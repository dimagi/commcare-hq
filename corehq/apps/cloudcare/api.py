import json
from couchdbkit.exceptions import ResourceNotFound
from django.contrib.humanize.templatetags.humanize import naturaltime
from casexml.apps.case.dbaccessors import get_open_case_ids_in_domain
from casexml.apps.case.util import iter_cases
from corehq.apps.cloudcare.exceptions import RemoteAppError
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain, \
    get_case_ids_in_domain_by_owner
from corehq.apps.users.models import CouchUser
from casexml.apps.case.models import CommCareCase, CASE_STATUS_ALL, CASE_STATUS_CLOSED, CASE_STATUS_OPEN
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import ApplicationBase
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch.safe_index import safe_index
from casexml.apps.phone.caselogic import get_footprint, get_related_cases
from datetime import datetime
from corehq.elastic import get_es_new, ES_META
import urllib
from django.utils.translation import ugettext as _
from dimagi.utils.parsing import json_format_date
from touchforms.formplayer.models import EntrySession
from django.core.urlresolvers import reverse

CLOUDCARE_API_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'  # todo: add '.%fZ'?


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
    def __init__(self, id=None, couch_doc=None, id_only=False, lite=True, sanitize=True):
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
            self._id = self._couch_doc['_id']
        return self._id

    @property
    def couch_doc(self):
        if self._couch_doc is None:
            self._couch_doc = CommCareCase.get(self._id)
        return self._couch_doc

    @property
    def case_json(self):
        json = self.couch_doc.get_json(lite=self.lite)
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
            json = _sanitize(json)
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
            base_results = [CaseAPIResult(couch_doc=case, id_only=self.ids_only)
                            for case in iter_cases(case_id_list, self.strip_history, self.wrap)]

        else:
            base_results = [CaseAPIResult(id=id, id_only=True) for id in case_id_list]

        if self.filters and not self.footprint:
            base_results = filter(_filter, base_results)

        if not self.footprint:
            return base_results

        case_list = [res.couch_doc for res in base_results]
        if self.footprint:
            case_list = get_footprint(
                            case_list,
                            self.domain,
                            strip_history=self.strip_history,
                        ).values()

        return [CaseAPIResult(couch_doc=case, id_only=self.ids_only) for case in case_list]

    def get_all(self):
        status = self.status or CASE_STATUS_ALL
        if status == CASE_STATUS_ALL:
            case_ids = get_case_ids_in_domain(self.domain, type=self.case_type)
        elif status == CASE_STATUS_OPEN:
            case_ids = get_open_case_ids_in_domain(self.domain, type=self.case_type)
        elif status == CASE_STATUS_CLOSED:
            _assert = soft_assert('@'.join(['droberts', 'dimagi.com']))
            _assert(False, "I'm surprised CaseAPIHelper "
                           "ever gets called with status=closed")
            # this is rare so we don't care if it requires two calls to get
            # all the ids
            case_ids = (
                set(get_case_ids_in_domain(self.domain, type=self.case_type))
                - set(get_open_case_ids_in_domain(self.domain, type=self.case_type))
            )
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

        ids = get_case_ids_in_domain_by_owner(
            self.domain, owner_id__in=owner_ids, closed=closed)

        return self._case_results(ids)


# todo: Make these api functions use generators for streaming
# so that a limit call won't fetch more docs than it needs to
# This could be achieved with something like CommCareCase.paging_view that
# returns a generator but internally batches couch requests
# potentially doubling the batch-size each time in case it really is a lot of data


def get_filtered_cases(domain, status, user_id=None, case_type=None,
                       filters=None, footprint=False, ids_only=False,
                       strip_history=True):

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
                            'ids_only', 'use_cache', 'hsph_hack']:
        if system_property in filters:
            del filters[system_property]
    return filters

def get_cloudcare_apps(domain):
    return map(lambda app: app._doc,
               ApplicationBase.view('cloudcare/cloudcare_apps', 
                                    startkey=[domain], endkey=[domain, {}]))

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
    app = filter(lambda x: x['name'] == app_name, apps)
    if app:
        return look_up_app_json(domain, app[0]['_id'])
    else:
        raise ResourceNotFound(_("Not found application by name: %s") % app_name)


def get_open_form_sessions(user, skip=0, limit=10):
    def session_to_json(sess):
        return {
            'id': sess.session_id,
            'app_id': sess.app_id,
            'name': sess.session_name,
            'display': u'{name} ({when})'.format(name=sess.session_name, when=naturaltime(sess.last_activity_date)),
            'created_date': sess.created_date.strftime(CLOUDCARE_API_DATETIME_FORMAT),
            'last_activity_date': sess.last_activity_date.strftime(CLOUDCARE_API_DATETIME_FORMAT),
        }
    return [session_to_json(sess) for sess in EntrySession.objects.filter(
        last_activity_date__isnull=False,
        user=user,
    ).order_by('-last_activity_date')[skip:limit]]


def get_cloudcare_form_url(domain, app_build_id=None, module_id=None, form_id=None, case_id=None):
    url_root = reverse("cloudcare_main", args=[domain, ""])
    url = url_root
    if app_build_id != None:
        url = url + "view/" + str(app_build_id)
        if module_id != None:
            url = url + "/" + str(module_id)
            if form_id != None:
                url = url + "/" + str(form_id)
                if case_id != None:
                    url = url + "/case/" + str(case_id)
    return url
