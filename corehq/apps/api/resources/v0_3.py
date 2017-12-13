from __future__ import absolute_import
from tastypie import fields

from casexml.apps.case.models import CommCareCase
from corehq.apps.api.resources import DomainSpecificResourceMixin
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import object_does_not_exist, get_obj
from corehq.apps.cloudcare.api import es_filter_cases
from corehq.apps.users.models import Permissions
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class CaseListFilters(object):
    format = 'json'
    
    def __init__(self, params):
        self.filters = dict((k, v) for k, v in params.items())

        #hacky hack for v0.3.
        #for v0.4, the API will explicitly require name and type
        #for this version, magically behind the scenes override the query for case_name and case_type to be name, type
        #note, on return output, the name will return as case_name, and type will return as case_type

        if 'case_name' in self.filters:
            self.filters['name'] = self.filters['case_name']
            del(self.filters['case_name'])
        if 'case_type' in self.filters:
            self.filters['type'] = self.filters['case_type']
            del(self.filters['case_type'])

        if 'format' in self.filters:
            self.format = self.filters['format']
            del self.filters['format']

        if 'order_by' in self.filters:
            del self.filters['order_by']


class CommCareCaseResource(HqBaseResource, DomainSpecificResourceMixin):
    type = "case"
    id = fields.CharField(attribute='case_id', readonly=True, unique=True)
    case_id = id
    user_id = fields.CharField(attribute='user_id', null=True)
    date_modified = fields.CharField(attribute='date_modified', default="1900-01-01")
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='closed_on', null=True)

    server_date_modified = fields.CharField(attribute='server_date_modified', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_date_opened', null=True)

    xform_ids = fields.ListField(attribute='xform_ids')

    properties = fields.DictField()

    def dehydrate_properties(self, bundle):
        return bundle.obj.get_properties_in_api_format()

    indices = fields.DictField()

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_index_map()

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).case_id
        }

    def obj_get(self, bundle, **kwargs):
        case_id = kwargs['pk']
        try:
            return CaseAccessors(kwargs['domain']).get_case(case_id)
        except CaseNotFound:
            raise object_does_not_exist("CommCareCase", case_id)

    def obj_get_list(self, bundle, domain, **kwargs):
        filters = CaseListFilters(bundle.request.GET)
        return es_filter_cases(domain, filters=filters.filters)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        object_class = CommCareCase
        resource_name = 'case'
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
