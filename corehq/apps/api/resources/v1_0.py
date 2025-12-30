from datetime import datetime

from django.http import JsonResponse
from django.urls import re_path as url
from django.urls import reverse

from tastypie import fields
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.http import HttpNotFound

from corehq import toggles
from corehq.apps.api.resources.auth import RequirePermissionAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.validation import (
    WebUserResourceSpec,
    WebUserValidationException,
)
from corehq.apps.export.const import CASE_EXPORT, FORM_EXPORT
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.export.views.download import DownloadDETSchemaView
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.util import (
    get_tableau_group_ids_by_names,
    get_tableau_groups_by_ids,
)
from corehq.apps.users.model_log import InviteModelAction
from corehq.apps.users.models import CouchUser, HqPermissions, Invitation
from corehq.apps.users.role_utils import (
    get_commcare_analytics_access_for_user_domain,
)
from corehq.apps.users.views import InviteWebUserView
from corehq.const import INVITATION_CHANGE_VIA_API

from . import CouchResourceMixin, DomainSpecificResourceMixin, HqBaseResource


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

        if not (user and user.is_member_of(domain) and user.is_active_in_domain(domain)):
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


class DETExportInstanceResource(
    CouchResourceMixin,
    HqBaseResource,
    DomainSpecificResourceMixin,
):
    """
    API resource to list ``FormExportInstance`` and ``CaseExportInstance``
    objects where ``show_det_config_download`` is True.

    This is used by CommCare Data Pipeline (formerly CommCare Sync) to
    list exports available for the Data Export Tool.
    """
    id = fields.CharField(attribute='_id', readonly=True, unique=True)
    name = fields.CharField(attribute='name', readonly=True)
    type = fields.CharField(readonly=True)
    export_format = fields.CharField(attribute='export_format', readonly=True)
    is_deidentified = fields.BooleanField(attribute='is_deidentified', readonly=True)
    case_type = fields.CharField(readonly=True, null=True)
    xmlns = fields.CharField(readonly=True, null=True)
    det_config_url = fields.CharField(readonly=True)

    class Meta(CustomResourceMeta):
        resource_name = 'det_export_instance'
        authentication = RequirePermissionAuthentication(HqPermissions.view_reports)
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']

    def dehydrate_det_config_url(self, bundle):
        return reverse(
            DownloadDETSchemaView.urlname,
            args=(bundle.request.domain, bundle.obj._id),
        )

    def dehydrate_type(self, bundle):
        """Return 'form' or 'case' based on the export instance type"""
        if isinstance(bundle.obj, FormExportInstance):
            return FORM_EXPORT
        elif isinstance(bundle.obj, CaseExportInstance):
            return CASE_EXPORT
        return None

    def dehydrate_case_type(self, bundle):
        """Return case_type for CaseExportInstance, None otherwise"""
        if isinstance(bundle.obj, CaseExportInstance):
            return bundle.obj.case_type
        return None

    def dehydrate_xmlns(self, bundle):
        """Return xmlns for FormExportInstance, None otherwise"""
        if isinstance(bundle.obj, FormExportInstance):
            return bundle.obj.xmlns
        return None

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']

        form_key = [domain, 'FormExportInstance']
        form_results = FormExportInstance.get_db().view(
            'export_instances_by_domain/view',
            startkey=form_key,
            endkey=form_key + [{}],
            include_docs=True,
            reduce=False
        ).all()
        form_exports = (
            _wrap_or_none(FormExportInstance, result['doc'])
            for result in form_results
            if result['doc'].get('show_det_config_download', False)
        )
        form_exports = [exp for exp in form_exports if exp]
        case_key = [domain, 'CaseExportInstance']
        case_results = CaseExportInstance.get_db().view(
            'export_instances_by_domain/view',
            startkey=case_key,
            endkey=case_key + [{}],
            include_docs=True,
            reduce=False
        ).all()
        case_exports = (
            _wrap_or_none(CaseExportInstance, result['doc'])
            for result in case_results
            if result['doc'].get('show_det_config_download', False)
        )
        case_exports = [exp for exp in case_exports if exp]

        return form_exports + case_exports

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']

        try:
            export = FormExportInstance.get(pk)
            if (
                export.doc_type == 'FormExportInstance'
                and export.domain == domain
                and export.show_det_config_download
            ):
                return export
        except Exception:
            pass

        try:
            export = CaseExportInstance.get(pk)
            if (
                export.doc_type == 'CaseExportInstance'
                and export.domain == domain
                and export.show_det_config_download
            ):
                return export
        except Exception:
            pass

        raise ImmediateHttpResponse(HttpNotFound())


def _wrap_or_none(class_, doc):
    """
    Returns ``class_.wrap(doc)``. If ``doc`` is malformed, returns ``None``.
    """
    try:
        return class_.wrap(doc)
    except Exception:
        return None
