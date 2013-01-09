from tastypie import fields
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.cloudcare.api import get_filtered_cases, get_filters_from_request,\
    api_closed_to_status
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource

class dict_object(object):
    def __init__(self, dict):
        self.dict = dict

    def __getattr__(self, item):
        return self.dict[item]

class CommCareCaseResource(JsonResource):
    type = "case"
    id = fields.CharField(attribute='case_id', readonly=True, unique=True)
    case_id = id
    user_id = fields.CharField(attribute='user_id')
    date_modified = fields.CharField(attribute='date_modified')
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='date_closed', null=True)

    server_date_modified = fields.CharField(attribute='server_date_modified')
    server_date_opened = fields.CharField(attribute='server_date_opened', null=True)

    xform_ids = fields.ListField(attribute='xform_ids')

    properties = fields.DictField('properties')

    indices = fields.DictField('indices')

    def obj_get(self, request, **kwargs):
        case = get_object_or_not_exist(CommCareCase, kwargs['pk'],
                                       kwargs['domain'])
        return dict_object(case.get_json())

    def obj_get_list(self, request, domain, **kwargs):
        user_id = request.GET.get('user_id')
        status = api_closed_to_status(request.REQUEST.get('closed', 'false'))
        filters = get_filters_from_request(request, limit_top_level=self.fields)
        case_type = filters.get('properties/case_type', None)
        return map(dict_object, get_filtered_cases(domain, status=status,
                                                   case_type=case_type,
                                                   user_id=user_id,
                                                   filters=filters))

    class Meta(CustomResourceMeta):
        resource_name = 'case'
