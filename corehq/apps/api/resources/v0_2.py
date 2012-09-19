from django.core.exceptions import ObjectDoesNotExist
from tastypie.resources import Resource
from tastypie import fields
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.cloudcare.api import get_filtered_cases, get_filters_from_request
from dimagi.utils.decorators import inline

class dict_object(object):
    def __init__(self, dict):
        self.dict = dict

    def __getattr__(self, item):
        return self.dict[item]

class CommCareCaseResource(Resource):
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

    indices = fields.ListField('indices')

    def obj_get(self, request, **kwargs):
        case = CommCareCase.get(kwargs['pk'])
        # stupid "security"
        if case.domain == kwargs['domain'] and case.doc_type == 'CommCareCase':
            return dict_object(case.get_json())
        else:
            raise ObjectDoesNotExist()

    def obj_get_list(self, request, domain, **kwargs):
        """"""
        user_id = request.GET.get('user_id')
        filters = get_filters_from_request(request, limit_top_level=self.fields)
        return map(dict_object, get_filtered_cases(domain, user_id=user_id, filters=filters))

    class Meta(CustomResourceMeta):
        resource_name = 'case'
