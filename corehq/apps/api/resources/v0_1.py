
# Standard library imports
from functools import wraps
import json

# Django imports
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.conf import settings

# Tastypie imports
from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.exceptions import BadRequest
from tastypie.throttle import CacheThrottle

# External imports
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.decorators import require_permission, require_permission_raw
from couchforms.models import XFormInstance

# CCHQ imports
from corehq.apps.domain.decorators import login_or_digest, login_or_basic
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser, WebUser, Permissions

# API imports
from corehq.apps.api.serializers import CustomXMLSerializer, XFormInstanceSerializer
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource, DomainSpecificResourceMixin


def determine_authtype(request):
    """
    Guess the auth type, based on request.
    """
    auth_header = (request.META.get('HTTP_AUTHORIZATION') or '').lower()
    if auth_header.startswith('basic '):
        return 'basic'
    elif auth_header.startswith('digest '):
        return 'digest'

    # the initial digest request doesn't have any authorization, so default to
    # digest in order to send back
    return 'digest'


def api_auth(view_func):
    @wraps(view_func)
    def _inner(req, domain, *args, **kwargs):
        try:
            return view_func(req, domain, *args, **kwargs)
        except Http404, ex:
            if ex.message:
                return HttpResponse(json.dumps({"error": ex.message}),
                                content_type="application/json",
                                status=404)
            return HttpResponse(json.dumps({"error": "not authorized"}),
                                content_type="application/json",
                                status=401)
    return _inner


class LoginAndDomainAuthentication(Authentication):

    def is_authenticated(self, request, **kwargs):
        return self._auth_test(request, wrappers=[self._get_auth_decorator(request), api_auth], **kwargs)

    def _get_auth_decorator(self, request):
        decorator_map = {
            'digest': login_or_digest,
            'basic': login_or_basic,
        }
        return decorator_map[determine_authtype(request)]

    def _auth_test(self, request, wrappers, **kwargs):
        PASSED_AUTH = 'is_authenticated'
        def dummy(request, domain, **kwargs):
            return PASSED_AUTH

        wrapped_dummy = dummy
        for wrapper in wrappers:
            wrapped_dummy = wrapper(wrapped_dummy)

        if not kwargs.has_key('domain'):
            kwargs['domain'] = request.domain

        try:
            response = wrapped_dummy(request, **kwargs)
        except PermissionDenied:
            response = HttpResponseForbidden()


        if response == PASSED_AUTH:
            return True
        else:
            return response

    def get_identifier(self, request):
        return request.couch_user.username


class RequirePermissionAuthentication(LoginAndDomainAuthentication):
    def __init__(self, permission, *args, **kwargs):
        super(RequirePermissionAuthentication, self).__init__(*args, **kwargs)
        self.permission = permission

    def is_authenticated(self, request, **kwargs):
        wrappers = [
            require_permission(self.permission, login_decorator=self._get_auth_decorator(request)),
            api_auth,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class DomainAdminAuthentication(LoginAndDomainAuthentication):

    def is_authenticated(self, request, **kwargs):
        permission_check = lambda couch_user, domain: couch_user.is_domain_admin(domain)
        wrappers = [
            require_permission_raw(permission_check, login_decorator=self._get_auth_decorator(request)),
            api_auth,
        ]
        return self._auth_test(request, wrappers=wrappers, **kwargs)


class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()
    default_format='application/json'
    throttle = CacheThrottle(throttle_at=getattr(settings, 'CCHQ_API_THROTTLE_REQUESTS', 25),
                             timeframe=getattr(settings, 'CCHQ_API_THROTTLE_TIMEFRAME', 15))

class UserResource(JsonResource, DomainSpecificResourceMixin):
    type = "user"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    username = fields.CharField(attribute='username', unique=True)
    first_name = fields.CharField(attribute='first_name', null=True)
    last_name = fields.CharField(attribute='last_name', null=True)
    default_phone_number = fields.CharField(attribute='default_phone_number', null=True)
    email = fields.CharField(attribute='email')
    phone_numbers = fields.ListField(attribute='phone_numbers')

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            user = self.Meta.object_class.get_by_user_id(pk, domain)
        except KeyError:
            user = None
        return user

    class Meta(CustomResourceMeta):
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']


class CommCareUserResource(UserResource):
    groups = fields.ListField(attribute='get_group_ids')
    user_data = fields.DictField(attribute='user_data')

    class Meta(UserResource.Meta):
        authentication = RequirePermissionAuthentication(Permissions.edit_commcare_users)
        object_class = CommCareUser
        resource_name = 'user'

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        group_id = bundle.request.GET.get('group')
        if group_id:
            group = Group.get(group_id)
            if not group or group.domain != domain:
                raise BadRequest('Project %s has no group with id=%s' % (domain, group_id))
            return list(group.get_users(only_commcare=True))
        else:
            return list(CommCareUser.by_domain(domain, strict=True))


class WebUserResource(UserResource):
    role = fields.CharField()
    is_admin = fields.BooleanField()
    permissions = fields.DictField()

    def dehydrate_role(self, bundle):
        return bundle.obj.get_role(bundle.request.domain).name

    def dehydrate_permissions(self, bundle):
        return bundle.obj.get_role(bundle.request.domain).permissions._doc

    def dehydrate_is_admin(self, bundle):
        return bundle.obj.is_domain_admin(bundle.request.domain)

    class Meta(UserResource.Meta):
        authentication = RequirePermissionAuthentication(Permissions.edit_web_users)
        object_class = WebUser
        resource_name = 'web-user'

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        username = bundle.request.GET.get('username')
        if username:
            user = WebUser.get_by_username(username)
            return [user] if user else []
        return list(WebUser.by_domain(domain))


class CommCareCaseResource(JsonResource, DomainSpecificResourceMixin):
    type = "case"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    user_id = fields.CharField(attribute='user_id')
    date_modified = fields.CharField(attribute='modified_on', null=True)
    closed = fields.BooleanField(attribute='closed')
    date_closed = fields.CharField(attribute='closed_on', null=True)

    xforms = fields.ListField(attribute='xform_ids')

    properties = fields.ListField()

    indices = fields.ListField(null=True)

    def dehydrate_properties(self, bundle):
        return bundle.obj.get_json()['properties']

    def dehydrate_indices(self, bundle):
        return bundle.obj.get_json()['indices']

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(CommCareCase, kwargs['pk'],
                                       kwargs['domain'])

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        closed_only = {
            'true': True,
            'false': False,
            'any': True
        }[bundle.request.GET.get('closed', 'false')]
        case_type = bundle.request.GET.get('case_type')

        key = [domain]
        if case_type:
            key.append(case_type)
        status = 'all' if closed_only else 'open'
        cases = CommCareCase.get_all_cases(domain, case_type=case_type, status=status, include_docs=True)
        return list(cases)


    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        object_class = CommCareCase
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'case'


class XFormInstanceResource(JsonResource, DomainSpecificResourceMixin):
    type = "form"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)

    form = fields.DictField(attribute='form')
    type = fields.CharField(attribute='type')
    version = fields.CharField(attribute='version')
    uiversion = fields.CharField(attribute='uiversion')
    metadata = fields.DictField(attribute='metadata', null=True)
    received_on = fields.DateTimeField(attribute="received_on")
    md5 = fields.CharField(attribute='xml_md5')

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(XFormInstance, kwargs['pk'], kwargs['domain'])

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        object_class = XFormInstance        
        list_allowed_methods = []
        detail_allowed_methods = ['get']
        resource_name = 'form'
        serializer = XFormInstanceSerializer()
