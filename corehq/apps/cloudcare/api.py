from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django.utils.translation import ugettext as _

from couchdbkit.exceptions import ResourceNotFound

from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_date

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.cloudcare.exceptions import RemoteAppError
from corehq.elastic import get_es_new, ES_META


CLOUDCARE_API_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'  # todo: add '.%fZ'?


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
