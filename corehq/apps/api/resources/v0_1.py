import datetime

from tastypie import fields
from tastypie.exceptions import BadRequest

from dimagi.utils.parsing import string_to_boolean

from corehq.apps.api.query_adapters import UserQuerySetAdapter
from corehq.apps.api.resources import (
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
)
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.es import FormES
from corehq.apps.groups.models import Group
from corehq.apps.user_importer.helpers import UserChangeLogger
from corehq.apps.users.models import CommCareUser, HqPermissions, WebUser
from corehq.const import USER_CHANGE_VIA_API


class UserResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    type = "user"
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    username = fields.CharField(attribute='username', unique=True)
    first_name = fields.CharField(attribute='first_name', null=True)
    last_name = fields.CharField(attribute='last_name', null=True)
    default_phone_number = fields.CharField(attribute='default_phone_number', null=True)
    email = fields.CharField(attribute='email')
    phone_numbers = fields.ListField(attribute='phone_numbers')
    eulas = fields.CharField(attribute='eulas', null=True)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            user = self.Meta.object_class.get_by_user_id(pk, domain)
        except KeyError:
            user = None
        return user

    @staticmethod
    def _get_user_change_logger(bundle):
        for_domain = bundle.obj.domain if bundle.obj.is_commcare_user() else None
        return UserChangeLogger(
            upload_domain=bundle.request.domain,
            user_domain=for_domain,
            user=bundle.obj,
            is_new_user=False,  # only used for tracking updates, creation already tracked by model's create method
            changed_by_user=bundle.request.couch_user,
            changed_via=USER_CHANGE_VIA_API,
            upload_record_id=None,
            user_domain_required_for_log=bundle.obj.is_commcare_user()
        )

    class Meta(CustomResourceMeta):
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']


class CommCareUserResource(UserResource):
    groups = fields.ListField(attribute='get_group_ids')
    user_data = fields.DictField(attribute='user_data')

    class Meta(UserResource.Meta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_commcare_users)
        object_class = CommCareUser
        resource_name = 'user'

    def dehydrate(self, bundle):
        show_extras = _safe_bool(bundle, 'extras')
        if show_extras:
            extras = {}
            now = datetime.datetime.utcnow()
            form_es_base = (FormES()
                .domain(bundle.request.domain)
                .user_id([bundle.obj._id])
            )

            extras['submitted_last_30'] = (form_es_base
                .submitted(gte=now - datetime.timedelta(days=30),
                           lte=now)
                .size(0).run()
            ).total
            extras['completed_last_30'] = (form_es_base
                .completed(gte=now - datetime.timedelta(days=30),
                           lte=now)
                .size(0).run()
            ).total
            first_of_this_month = datetime.datetime(now.year, now.month, 1)
            first_of_last_month = (first_of_this_month - datetime.timedelta(days=1)).replace(day=1)
            extras['submitted_last_month'] = (form_es_base
                .submitted(gte=first_of_last_month,
                           lte=first_of_this_month)
                .size(0).run()
            ).total
            extras['completed_last_month'] = (form_es_base
                .completed(gte=first_of_last_month,
                           lte=first_of_this_month)
                .size(0).run()
            ).total
            bundle.data['extras'] = extras
        return super(UserResource, self).dehydrate(bundle)

    def dehydrate_user_data(self, bundle):
        user_data = bundle.obj.get_user_data(bundle.obj.domain).to_dict()
        if self.determine_format(bundle.request) == 'application/xml':
            # attribute names can't start with digits in xml
            user_data = {k: v for k, v in user_data.items() if not k[0].isdigit()}
        return user_data

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        show_archived = _safe_bool(bundle, 'archived')
        group_id = bundle.request.GET.get('group')
        if group_id:
            group = Group.get(group_id)
            if not group or group.domain != domain:
                raise BadRequest('Project %s has no group with id=%s' % (domain, group_id))
            return list(group.get_users(only_commcare=True))
        else:
            return UserQuerySetAdapter(domain, show_archived=show_archived)


class WebUserResource(UserResource):
    role = fields.CharField()
    is_admin = fields.BooleanField()
    permissions = fields.DictField()

    def dehydrate_role(self, bundle):
        role = bundle.obj.get_role(bundle.request.domain)
        return role.name if role else ''

    def dehydrate_permissions(self, bundle):
        role = bundle.obj.get_role(bundle.request.domain)
        return role.permissions.to_json() if role else {}

    def dehydrate_is_admin(self, bundle):
        return bundle.obj.is_domain_admin(bundle.request.domain)

    class Meta(UserResource.Meta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_web_users)
        object_class = WebUser
        resource_name = 'web-user'

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        username = bundle.request.GET.get('web_username')
        if username:
            user = WebUser.get_by_username(username)
            if not (user and user.is_member_of(domain) and user.is_active):
                user = None
            return [user] if user else []
        return list(WebUser.by_domain(domain))


def _safe_bool(bundle, param, default=False):
    try:
        return string_to_boolean(bundle.request.GET.get(param))
    except ValueError:
        return default
