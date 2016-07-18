from tastypie import fields

from casexml.apps.case.models import CommCareCase

from corehq.apps.api.resources import (
    dict_object,
    DomainSpecificResourceMixin,
    HqBaseResource,
)
from corehq.apps.api.resources.v0_1 import (
    CustomResourceMeta,
    RequirePermissionAuthentication,
)
from corehq.apps.api.util import get_object_or_not_exist, get_obj
from corehq.apps.cloudcare.api import (
    api_closed_to_status,
    get_filtered_cases,
    get_filters_from_request_params,
)
from corehq.apps.users.models import Permissions


class CommCareCaseResource(HqBaseResource, DomainSpecificResourceMixin):
    type = "case"
    id = fields.CharField(attribute='case_id', readonly=True, unique=True)
    case_id = id
    user_id = fields.CharField(attribute='user_id')
    date_modified = fields.CharField(attribute='date_modified', default="1900-01-01")
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='closed_on', null=True)

    server_date_modified = fields.CharField(attribute='server_date_modified', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_date_opened', null=True)

    xform_ids = fields.ListField(attribute='xform_ids')

    properties = fields.DictField()

    def dehydrate_properties(self, bundle):
        return bundle.obj.properties

    indices = fields.DictField()

    def dehydrate_indices(self, bundle):
        return bundle.obj.indices

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).case_id
        }

    def obj_get(self, bundle, **kwargs):
        case = get_object_or_not_exist(CommCareCase, kwargs['pk'], kwargs['domain'])
        return dict_object(case.to_api_json())

    def obj_get_list(self, bundle, domain, **kwargs):
        user_id = bundle.request.GET.get('user_id')
        request_params = bundle.request.GET
        status = api_closed_to_status(request_params.get('closed', 'false'))
        filters = get_filters_from_request_params(request_params, limit_top_level=self.fields)
        case_type = filters.get('properties/case_type', None)
        return map(dict_object, get_filtered_cases(domain, status=status,
                                  case_type=case_type,
                                  user_id=user_id,
                                  filters=filters))

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        object_class = CommCareCase
        resource_name = 'case'
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
