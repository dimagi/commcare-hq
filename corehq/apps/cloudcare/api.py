import json
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase, CASE_STATUS_ALL, CASE_STATUS_CLOSED, CASE_STATUS_OPEN
from corehq.apps.locations.models import Location
from corehq.apps.app_manager.models import ApplicationBase, Application
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.decorators import inline
from casexml.apps.phone.caselogic import get_footprint, get_related_cases
from datetime import datetime
from corehq.elastic import get_es
import urllib
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.chunked import chunked

def api_closed_to_status(closed_string):
    # legacy api support
    return {
        'any': CASE_STATUS_ALL,
        'true': CASE_STATUS_CLOSED,
        'false': CASE_STATUS_OPEN,
    }[closed_string]

def closed_to_status(closed_bool):
    return {None: CASE_STATUS_ALL,
            True: CASE_STATUS_CLOSED,
            False: CASE_STATUS_OPEN}[closed_bool]

def status_to_closed_flags(status):
    return {CASE_STATUS_ALL: [True, False],
            CASE_STATUS_CLOSED: [True],
            CASE_STATUS_OPEN: [False]}[status]

class CaseAPIResult(object):
    """
    The result of a case API query. Useful for abstracting out the difference
    between an id-only representation and a full_blown one.
    """
    def __init__(self, id=None, couch_doc=None, id_only=False, lite=True):
        self._id = id
        self._couch_doc = couch_doc
        self.id_only = id_only
        self.lite = lite

    def __getitem__(self, key):
        if key == 'case_id':
            return self.id
        else:
            return self.case_json.__getitem__(key)

    @property
    def id(self):
        if self._id is None:
            self._id = self._couch_doc._id
        return self._id

    @property
    def couch_doc(self):
        if self._couch_doc is None:
            self._couch_doc = CommCareCase.get(self._id)
        return self._couch_doc

    @property
    def case_json(self):
        return self.couch_doc.get_json(lite=self.lite)

    def to_json(self):
        return self.id if self.id_only else self.case_json

class CaseAPIHelper(object):
    """
    Simple config object for querying the APIs
    """
    def __init__(self, domain, status=CASE_STATUS_OPEN, case_type=None, ids_only=False,
                 footprint=False, strip_history=False, filters=None, include_children=False):
        if status not in [CASE_STATUS_ALL, CASE_STATUS_CLOSED, CASE_STATUS_OPEN]:
            raise ValueError("invalid case status %s" % status)
        self.domain = domain
        self.status = status
        self.case_type = case_type
        self.ids_only = ids_only
        self.footprint = footprint
        self.strip_history = strip_history
        self.filters = filters
        self.include_children = include_children

    def iter_cases(self, ids):
        database = CommCareCase.get_db()
        if not self.strip_history:
            for doc in iter_docs(database, ids):
                yield CommCareCase.wrap(doc)
        else:
            for doc_ids in chunked(ids, 100):
                for case in CommCareCase.bulk_get_lite(doc_ids):
                    yield case

    def _case_results(self, case_id_list):
        def _filter(res):
            if self.filters:
                for path, val in self.filters.items():
                    actual_val = safe_index(res.case_json, path.split("/"))
                    if actual_val != val:
                        # closed=false => case.closed == False
                        if val in ('null', 'true', 'false'):
                            if actual_val != json.loads(val):
                                return False
                        else:
                            return False
                return True

        if not self.ids_only or self.filters or self.footprint:
            # optimization hack - we know we'll need the full cases eventually
            # so just grab them now.
            base_results = [CaseAPIResult(couch_doc=case, id_only=self.ids_only) \
                            for case in self.iter_cases(case_id_list)]
        else:
            base_results = [CaseAPIResult(id=id, id_only=True) for id in case_id_list]

        if self.filters:
            base_results = filter(_filter, base_results)

        link_locations(base_results)

        if not self.footprint and not self.include_children:
            return base_results

        case_list = [res.couch_doc for res in base_results]
        if self.footprint:
            case_list = get_footprint(
                            case_list,
                            self.domain,
                            strip_history=self.strip_history,
                        ).values()

        if self.include_children:
            case_list = get_related_cases(
                            case_list,
                            self.domain,
                            strip_history=self.strip_history,
                            search_up=False,
                        ).values()

        return [CaseAPIResult(couch_doc=case, id_only=self.ids_only) for case in case_list]

    def get_all(self):
        view_results = CommCareCase.get_all_cases(self.domain, case_type=self.case_type, status=self.status)
        ids = [res["id"] for res in view_results]
        return self._case_results(ids)

    def get_owned(self, user_id):
        try:
            user = CouchUser.get_by_user_id(user_id, self.domain)
        except KeyError:
            user = None
        try:
            owner_ids = user.get_owner_ids()
        except AttributeError:
            owner_ids = [user_id]

        @list
        @inline
        def keys():
            for owner_id in owner_ids:
                for bool in status_to_closed_flags(self.status):
                    yield [self.domain, owner_id, bool]

        view_results = CommCareCase.view('hqcase/by_owner', keys=keys,
                                         include_docs=False, reduce=False)
        ids = [res["id"] for res in view_results]
        return self._case_results(ids)

def link_locations(base_results):
    """annotate case results with info from linked location doc (if any)"""

    def _has_location(doc):
        return hasattr(doc, 'location_') and doc.location_

    loc_ids = set(match.couch_doc.location_[-1] for match in base_results if _has_location(match.couch_doc))
    locs = dict((loc._id, loc) for loc in Location.view('_all_docs', keys=list(loc_ids), include_docs=True))
    for match in base_results:
        if _has_location(match.couch_doc):
            loc_id = match.couch_doc.location_[-1]
            match.couch_doc.linked_location = locs[loc_id]._doc

# todo: Make these api functions use generators for streaming
# so that a limit call won't fetch more docs than it needs to
# This could be achieved with something like CommCareCase.paging_view that
# returns a generator but internally batches couch requests
# potentially doubling the batch-size each time in case it really is a lot of data


def get_filtered_cases(domain, status, user_id=None, case_type=None,
                       filters=None, footprint=False, ids_only=False,
                       strip_history=True, include_children=False):

    # for now, a filter value of None means don't filter
    filters = dict((k, v) for k, v in (filters or {}).items() if v is not None)
    helper = CaseAPIHelper(domain, status, case_type=case_type, ids_only=ids_only,
                           footprint=footprint, strip_history=strip_history,
                           filters=filters, include_children=include_children)

    if user_id:
        return helper.get_owned(user_id)
    else:
        return helper.get_all()

class ElasticCaseQuery(object):
    # this class is currently pretty customized to serve exactly
    # this API. one day it may be worth reconciling our ES interfaces
    # but today is not that day.
    # To be replaced by CaseES framework.
    RESERVED_KEYS = ('date_modified_start', 'date_modified_end', 
                     'server_date_modified_start', 'server_date_modified_end', 
                     'limit', 'offset')
    
    def __init__(self, domain, filters):
        self.domain = domain
        self.filters = filters
        self.offset = int(filters.get('offset', 0))
        self.limit = int(filters.get('limit', 50))
        self._date_modified_start = filters.get("date_modified_start", None)
        self._date_modified_end = filters.get("date_modified_end", None)
        self._server_date_modified_start = filters.get("server_date_modified_start", None)
        self._server_date_modified_end = filters.get("server_date_modified_end", None)
        
    @property
    def uses_modified(self):
        return bool(self._date_modified_start or self._date_modified_end)
        
    @property
    def uses_server_modified(self):
        return bool(self._server_date_modified_start or self._server_date_modified_end)
        
    @property
    def date_modified_start(self):
        return self._date_modified_start or datetime(1970,1,1).strftime("%Y-%m-%d")
        
    @property
    def date_modified_end(self):
        return self._date_modified_end or datetime.max.strftime("%Y-%m-%d")
        
    @property
    def server_date_modified_start(self):
        return self._server_date_modified_start or datetime(1970,1,1).strftime("%Y-%m-%d")
        
    @property
    def server_date_modified_end(self):
        return self._server_date_modified_end or datetime.max.strftime("%Y-%m-%d")
        
    @property
    def scrubbed_filters(self):
        return dict( (k, v) for k, v in self.filters.items()
                     if k not in self.RESERVED_KEYS and not k.endswith('__full') )
        
    def _modified_params(self, key, start, end):
        return {
            'range': {
                key: {
                    'from': start,
                    'to': end
                }
            }
        }
        
    @property
    def modified_params(self, ):
        return self._modified_params('modified_on',
                                     self.date_modified_start,
                                     self.date_modified_end)
        
    @property
    def server_modified_params(self):
        return self._modified_params('server_modified_on',
                                     self.server_date_modified_start,
                                     self.server_date_modified_end)
        
    def get_terms(self):
        yield {'term': {'domain.exact': self.domain}}
        if self.uses_modified:
            yield self.modified_params
        if self.uses_modified:
            yield self.modified_params
        if self.uses_server_modified:
            yield self.server_modified_params
        for k, v in self.scrubbed_filters.items():
            yield {'term': {k: v.lower()}}

    def get_query(self):
        return {
            'query': {
                'bool': {
                    'must': list(self.get_terms())
                }
            },
            'sort': {
                'modified_on': {'order': 'asc'}
            },
            'from': self.offset,
            'size': self.offset + self.limit,
        }

def es_filter_cases(domain, filters=None):
    """
    Filter cases using elastic search
    (Domain, Filters?) -> [CommCareCase]
    """
    
    
    q = ElasticCaseQuery(domain, filters)
    res = get_es().get('hqcases/_search', data=q.get_query())
    # this is ugly, but for consistency / ease of deployment just
    # use this to return everything in the expected format for now
    return [CommCareCase.wrap(r["_source"]) for r in res['hits']['hits'] if r["_source"]]

def get_filters_from_request(request, limit_top_level=None):
    """
    limit_top_level lets you specify a whitelist of top-level properties you can include in the filters,
    properties with a / in them are always included in the filters
    """
    def _decode(thing):
        try:
            return urllib.unquote(thing)
        except Exception:
            return thing
    
    # super weird hack: force decoding keys because sometimes (only seen in 
    # production) django doesn't do this for us.
    filters = dict((_decode(k), v) for k, v in request.REQUEST.items())
    if limit_top_level is not None:
        filters = dict([(key, val) for key, val in filters.items() if '/' in key or key in limit_top_level])

    for system_property in ['user_id', 'closed', 'format', 'footprint',
                            'ids_only', 'include_children']:
        if system_property in filters:
            del filters[system_property]
    return filters

def get_cloudcare_apps(domain):
    return map(lambda app: app._doc,
               ApplicationBase.view('cloudcare/cloudcare_apps', 
                                    startkey=[domain], endkey=[domain, {}]))

def get_app_json(app):
    app_json = app.to_json()
    app_json['post_url'] = app.post_url
    return app_json

def look_up_app_json(domain, app_id):
    app = Application.get(app_id)
    assert(app.domain == domain)
    return get_app_json(app)
