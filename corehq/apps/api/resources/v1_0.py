from datetime import datetime

from django.http import JsonResponse
from django.urls import re_path as url

from tastypie import fields
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpNotFound
from . import (
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
)
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.users.role_utils import get_commcare_analytics_access_for_user_domain
from corehq import toggles
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import (
    CouchUser,
    HqPermissions,
    Invitation,
)
from corehq.apps.users.model_log import InviteModelAction
from corehq.apps.users.views import InviteWebUserView
from corehq.apps.reports.util import (
    get_tableau_group_ids_by_names,
    get_tableau_groups_by_ids,
)
from corehq.apps.api.validation import WebUserResourceSpec, WebUserValidationException

from corehq.const import INVITATION_CHANGE_VIA_API


class CommCareAnalyticsUserResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):

    roles = fields.ListField()
    permissions = fields.DictField()

    class Meta(CustomResourceMeta):
        resource_name = 'analytics-roles'
        detail_allowed_methods = ['get']

    def dehydrate(self, bundle):
        cca_access = get_commcare_analytics_access_for_user_domain(bundle.obj, bundle.request.domain)

        bundle.data['roles'] = cca_access['roles']
        bundle.data['permissions'] = cca_access['permissions']

        return bundle

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        if not toggles.SUPERSET_ANALYTICS.enabled(domain):
            raise ImmediateHttpResponse(
                HttpNotFound()
            )

        user = CouchUser.get_by_username(bundle.request.user.username)

        if not (user and user.is_member_of(domain) and user.is_active):
            return None
        return user

    def prepend_urls(self):
        # We're overriding the default "list" view to redirect to "detail" view since
        # we already know the user through OAuth.
        return [
            url(r"^$", self.wrap_view('dispatch_detail'), name='api_dispatch_detail'),
        ]


class InvitationResource(HqBaseResource, DomainSpecificResourceMixin):
    id = fields.CharField(attribute='uuid', readonly=True, unique=True)
    email = fields.CharField(attribute='email')
    role = fields.CharField()
    primary_location_id = fields.CharField(attribute='primary_location_id', null=True)
    assigned_location_ids = fields.ListField(null=True)
    profile = fields.CharField(null=True)
    user_data = fields.DictField(attribute='custom_user_data')
    tableau_role = fields.CharField(attribute='tableau_role', null=True)
    tableau_groups = fields.ListField(null=True)

    class Meta(CustomResourceMeta):
        resource_name = "invitation"
        authentication = RequirePermissionAuthentication(HqPermissions.edit_web_users)
        allowed_methods = ['post']
        always_return_data = True

    def dehydrate_role(self, bundle):
        return bundle.obj.get_role_name()

    def dehydrate_assigned_location_ids(self, bundle):
        return list(bundle.obj.assigned_locations.values_list('location_id', flat=True))

    def dehydrate_tableau_groups(self, bundle):
        return [group.name for group in get_tableau_groups_by_ids(bundle.obj.tableau_group_ids,
                                                                 bundle.request.domain)]

    def dehydrate_profile(self, bundle):
        if bundle.obj.profile:
            return bundle.obj.profile.name

    def obj_create(self, bundle, **kwargs):
        domain = kwargs['domain']
        try:
            spec = WebUserResourceSpec(
                domain=domain,
                requesting_user=bundle.request.couch_user,
                email=bundle.data.get('email'),
                is_post=True,
                role=bundle.data.get('role'),
                primary_location_id=bundle.data.get('primary_location_id'),
                assigned_location_ids=bundle.data.get('assigned_location_ids'),
                new_or_existing_profile_name=bundle.data.get('profile'),
                new_or_existing_user_data=bundle.data.get('user_data', {}),
                tableau_role=bundle.data.get('tableau_role'),
                tableau_groups=bundle.data.get('tableau_groups'),
                parameters=bundle.data.keys(),
            )
        except WebUserValidationException as e:
            raise ImmediateHttpResponse(JsonResponse({"errors": e.message}, status=400))

        profile = spec.profiles_by_name.get(spec.new_or_existing_profile_name)
        role_id = spec.roles_by_name.get(spec.role)
        tableau_group_ids = get_tableau_group_ids_by_names(spec.tableau_groups or [], domain)

        primary_loc_id = None
        assigned_locs = []
        if spec.assigned_location_ids:
            primary_loc_id = spec.primary_location_id
            assigned_locs = SQLLocation.active_objects.filter(
                location_id__in=spec.assigned_location_ids, domain=domain)
            real_ids = [loc.location_id for loc in assigned_locs]

            if missing_ids := set(spec.assigned_location_ids) - set(real_ids):
                raise ImmediateHttpResponse(JsonResponse(
                    {"error": f"Could not find location ids: {', '.join(missing_ids)}."}, status=400))
        initial_fields = {
            'domain': domain,
            'email': spec.email.lower(),
            'custom_user_data': spec.new_or_existing_user_data or {},
            'invited_by': bundle.request.couch_user.user_id,
            'invited_on': datetime.utcnow(),
            'tableau_role': spec.tableau_role,
            'tableau_group_ids': tableau_group_ids,
        }
        invite_params = {
            'role': role_id,
            'primary_location_id': primary_loc_id,
            'profile': profile,
        }
        invite_params.update(initial_fields)
        invite = Invitation.objects.create(**invite_params)
        invite.assigned_locations.set(assigned_locs)

        # Log invite creation
        primary_loc = None
        if primary_loc_id:
            primary_loc = SQLLocation.objects.get(location_id=primary_loc_id)
        changes = InviteWebUserView.format_changes(domain,
                                                   {'role_name': spec.role,
                                                    'profile': profile,
                                                    'assigned_locations': assigned_locs,
                                                    'primary_location': primary_loc})
        changes.update(initial_fields)
        invite.save(logging_values={"changed_by": bundle.request.couch_user.user_id,
                                    "changed_via": INVITATION_CHANGE_VIA_API,
                                    "action": InviteModelAction.CREATE, "changes": changes})
        bundle.obj = invite
        return bundle
