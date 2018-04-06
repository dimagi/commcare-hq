from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import json
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error

from django.urls import reverse
from django.utils.translation import ugettext as _

from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.models import CommCareCase, CASE_STATUS_ALL, CASE_STATUS_CLOSED, CASE_STATUS_OPEN
from casexml.apps.case.util import iter_cases
from casexml.apps.phone.cleanliness import get_dependent_case_info
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils.general import should_use_sql_backend
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.parsing import json_format_date

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.cloudcare.exceptions import RemoteAppError
from corehq.apps.users.models import CouchUser
from corehq.elastic import get_es_new, ES_META
from six.moves import filter


CLOUDCARE_API_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'  # todo: add '.%fZ'?


def api_closed_to_status(closed_string):
    # legacy api support
    return {
        'any': CASE_STATUS_ALL,
        'true': CASE_STATUS_CLOSED,
        'false': CASE_STATUS_OPEN,
    }[closed_string]


class CaseAPIResult(object):
    """
    The result of a case API query. Useful for abstracting out the difference
    between an id-only representation and a full_blown one.
    """

    def __init__(self, domain, id=None, couch_doc=None, id_only=False, lite=True, sanitize=True):
        self.domain = domain
        self._id = id
        self._couch_doc = couch_doc
        self.id_only = id_only
        self.lite = lite
        self.sanitize = sanitize

    def __getitem__(self, key):
        if key == 'case_id':
            return self.id
        else:
            return self.case_json.__getitem__(key)

    @property
    def id(self):
        if self._id is None:
            self._id = self._couch_doc['_id'] if isinstance(self._couch_doc, dict) else self._couch_doc.case_id
        return self._id

    @property
    def couch_doc(self):
        if self._couch_doc is None:
            self._couch_doc = CaseAccessors(self.domain).get_case(self._id)
        return self._couch_doc

    @property
    def case_json(self):
        json = self.couch_doc.to_api_json(lite=self.lite)
        if self.sanitize:
            # This ensures that any None value will be encoded as "" instead of null
            # This fixes http://manage.dimagi.com/default.asp?158655 because mobile chokes on null
            def _sanitize(props):
                for key, val in props.items():
                    if val is None:
                        props[key] = ''
                    elif isinstance(val, dict):
                        props[key] = _sanitize(val)
                return props
            json = _sanitize(dict(json))
        return json

    def to_json(self):
        return self.id if self.id_only else self.case_json


class CaseAPIHelper(object):
    """
    Simple config object for querying the APIs
    """

    def __init__(self, domain, status=CASE_STATUS_OPEN, case_type=None, ids_only=False,
                 footprint=False, strip_history=False, filters=None):
        if status not in [CASE_STATUS_ALL, CASE_STATUS_CLOSED, CASE_STATUS_OPEN]:
            raise ValueError("invalid case status %s" % status)
        self.domain = domain
        self.status = status
        self.case_type = case_type
        self.ids_only = ids_only
        self.wrap = not ids_only  # if we're just querying IDs we don't need to wrap the docs
        self.footprint = footprint
        self.strip_history = strip_history
        self.filters = filters
        self.case_accessors = CaseAccessors(self.domain)

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

        if self.filters and not self.footprint:
            base_results = self._populate_results(case_id_list)
            return list(filter(_filter, base_results))

        if self.footprint:
            initial_case_ids = set(case_id_list)
            dependent_case_ids = get_dependent_case_info(self.domain, initial_case_ids).all_ids
            all_case_ids = initial_case_ids | dependent_case_ids
        else:
            all_case_ids = case_id_list

        if self.ids_only:
            return [CaseAPIResult(domain=self.domain, id=case_id, id_only=True) for case_id in all_case_ids]
        else:
            return self._populate_results(all_case_ids)

    def _populate_results(self, case_id_list):
        if should_use_sql_backend(self.domain):
            base_results = [CaseAPIResult(domain=self.domain, couch_doc=case, id_only=self.ids_only)
                            for case in self.case_accessors.iter_cases(case_id_list)]
        else:
            base_results = [CaseAPIResult(domain=self.domain, couch_doc=case, id_only=self.ids_only)
                            for case in iter_cases(case_id_list, self.strip_history, self.wrap)]
        return base_results

    def get_all(self):
        status = self.status or CASE_STATUS_ALL
        if status == CASE_STATUS_ALL:
            case_ids = self.case_accessors.get_case_ids_in_domain(self.case_type)
        elif status == CASE_STATUS_OPEN:
            case_ids = self.case_accessors.get_open_case_ids_in_domain_by_type(self.case_type)
        else:
            raise ValueError("Invalid value for 'status': '%s'" % status)

        return self._case_results(case_ids)

    def get_owned(self, user_id):
        try:
            user = CouchUser.get_by_user_id(user_id, self.domain)
        except KeyError:
            user = None
        try:
            owner_ids = user.get_owner_ids()
        except AttributeError:
            owner_ids = [user_id]

        closed = {
            CASE_STATUS_OPEN: False,
            CASE_STATUS_CLOSED: True,
            CASE_STATUS_ALL: None,
        }[self.status]

        ids = self.case_accessors.get_case_ids_by_owners(owner_ids, closed=closed)
        return self._case_results(ids)


# todo: Make these api functions use generators for streaming
# so that a limit call won't fetch more docs than it needs to
# This could be achieved with something like CommCareCase.paging_view that
# returns a generator but internally batches couch requests
# potentially doubling the batch-size each time in case it really is a lot of data


def get_filtered_cases(domain, status, user_id=None, case_type=None,
                       filters=None, footprint=False, ids_only=False,
                       strip_history=True):

    # NOTE: filters get ignored if footprint=True
    # a filter value of None means don't filter
    filters = dict((k, v) for k, v in (filters or {}).items() if v is not None)
    helper = CaseAPIHelper(domain, status, case_type=case_type, ids_only=ids_only,
                           footprint=footprint, strip_history=strip_history,
                           filters=filters)
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
        return self._date_modified_start or json_format_date(datetime(1970, 1, 1))
        
    @property
    def date_modified_end(self):
        return self._date_modified_end or json_format_date(datetime.max)
        
    @property
    def server_date_modified_start(self):
        return self._server_date_modified_start or json_format_date(datetime(1970, 1, 1))
        
    @property
    def server_date_modified_end(self):
        return self._server_date_modified_end or json_format_date(datetime.max)
        
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
    meta = ES_META['cases']
    res = get_es_new().search(meta.index, body=q.get_query())
    # this is ugly, but for consistency / ease of deployment just
    # use this to return everything in the expected format for now
    return [CommCareCase.wrap(r["_source"]) for r in res['hits']['hits'] if r["_source"]]


def get_filters_from_request_params(request_params, limit_top_level=None):
    """
    limit_top_level lets you specify a whitelist of top-level properties you can include in the filters,
    properties with a / in them are always included in the filters
    """
    def _decode(thing):
        try:
            return six.moves.urllib.parse.unquote(thing)
        except Exception:
            return thing
    
    # super weird hack: force decoding keys because sometimes (only seen in 
    # production) django doesn't do this for us.
    filters = dict((_decode(k), v) for k, v in request_params.items())
    if limit_top_level is not None:
        filters = dict([(key, val) for key, val in filters.items() if '/' in key or key in limit_top_level])

    for system_property in ['user_id', 'closed', 'format', 'footprint',
                            'ids_only', 'use_cache', 'hsph_hack']:
        if system_property in filters:
            del filters[system_property]
    return filters


def get_app_json(app):
    if not app:
        return None
    app_json = app.to_json()
    app_json['post_url'] = app.post_url
    return app_json


def look_up_app_json(domain, app_id):
    app = get_app(domain, app_id)
    if app.is_remote_app():
        raise RemoteAppError()
    assert(app.domain == domain)
    return get_app_json(app)


def get_cloudcare_app(domain, app_name):
    apps = get_cloudcare_apps(domain)
    app = [x for x in apps if x['name'] == app_name]
    if app:
        return look_up_app_json(domain, app[0]['_id'])
    else:
        raise ResourceNotFound(_("Not found application by name: %s") % app_name)


def get_cloudcare_form_url(domain, app_build_id=None, module_id=None, form_id=None, case_id=None):
    return reverse("formplayer_main", args=[domain])
