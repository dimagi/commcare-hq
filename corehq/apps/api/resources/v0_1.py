from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.decorators import login_or_digest
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.exceptions import BadRequest
from tastypie.serializers import Serializer
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource


class CustomXMLSerializer(Serializer):
    def to_etree(self, data, options=None, name=None, depth=0):
        etree = super(CustomXMLSerializer, self).to_etree(data, options, name, depth)
        id = etree.find('id')
        if id is not None:
            etree.attrib['id'] = id.findtext('.')
            etree.remove(id)
        return etree


class LoginAndDomainAuthentication(Authentication):
    def is_authenticated(self, request, **kwargs):
        PASSED_AUTH = 'is_authenticated'

        @login_or_digest
        def dummy(request, domain, **kwargs):
            return PASSED_AUTH

        if not kwargs.has_key('domain'):
            kwargs['domain'] = request.domain

        response = dummy(request, **kwargs)

        if response == PASSED_AUTH:
            return True
        else:
            return response


    def get_identifier(self, request):
        return request.couch_user.username

class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()

class CommCareUserResource(JsonResource):
    type = "user"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    username = fields.CharField(attribute='username', unique=True)
    first_name = fields.CharField(attribute='first_name')
    last_name = fields.CharField(attribute='last_name')
    default_phone_number = fields.CharField(attribute='default_phone_number', null=True)
    email = fields.CharField(attribute='email')
    phone_numbers = fields.ListField(attribute='phone_numbers')
    groups = fields.ListField(attribute='get_group_ids')
    user_data = fields.DictField(attribute='user_data')

    def obj_get(self, request, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            user = CommCareUser.get_by_user_id(pk, domain)
        except KeyError:
            user = None
        return user

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        group_id = request.GET.get('group')
        if group_id:
            group = Group.get(group_id)
            if not group or group.domain != domain:
                raise BadRequest('Project %s has no group with id=%s' % (domain, group_id))
            return list(group.get_users(only_commcare=True))
        else:
            return list(CommCareUser.by_domain(domain))

    class Meta(CustomResourceMeta):
        resource_name = 'user'

class CommCareCaseResource(JsonResource):
    type = "case"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    user_id = fields.CharField(attribute='user_id')
    date_modified = fields.CharField(attribute='modified_on')
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='closed_on', null=True)

    xforms = fields.ListField(attribute='xform_ids')

    properties = fields.ListField()

    indices = fields.ListField(null=True)

    def dehydrate_properties(self, bundle):
        return bundle.obj.get_json()['properties']

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_json()['indices']

    def obj_get(self, request, **kwargs):
        return get_object_or_not_exist(CommCareCase, kwargs['pk'],
                                       kwargs['domain'])

    def obj_get_list(self, request, **kwargs):
        domain = kwargs['domain']
        closed_only = {
                          'true': True,
                          'false': False,
                          'any': True
                      }[request.GET.get('closed', 'false')]
        case_type = request.GET.get('case_type')

        key = [domain]
        if case_type:
            key.append(case_type)
        cases = CommCareCase.view('hqcase/all_cases' if closed_only else 'hqcase/open_cases',
                                  startkey=key,
                                  endkey=key + [{}],
                                  include_docs=True,
                                  reduce=False,
        ).all()

        return list(cases)


    class Meta(CustomResourceMeta):
        resource_name = 'case'

class XFormInstanceResource(JsonResource):
    type = "form"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)

    form = fields.DictField(attribute='get_form')
    type = fields.CharField(attribute='type')
    version = fields.CharField(attribute='version')
    uiversion = fields.CharField(attribute='uiversion')
    metadata = fields.DictField(attribute='metadata')
    received_on = fields.DateTimeField(attribute="received_on")
    md5 = fields.CharField(attribute='xml_md5')

    def obj_get(self, request, **kwargs):
        return get_object_or_not_exist(XFormInstance, kwargs['pk'], kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'form'
