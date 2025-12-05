import json
from django.contrib import messages
from django.http import (
    Http404,
    JsonResponse,
)
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy, gettext as _, ngettext
from django.views.decorators.http import require_POST
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps, get_application_access_for_domain
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.registry.utils import get_data_registry_dropdown_options
from corehq.apps.reports.models import TableauVisualization
from corehq.apps.reports.util import get_possible_reports
from corehq.apps.userreports.util import has_report_builder_access
from corehq.apps.users.analytics import get_role_user_count
from corehq.apps.users.decorators import require_can_view_roles
from corehq.apps.users.exceptions import InvalidRequestException
from corehq.apps.users.landing_pages import get_allowed_landing_pages, validate_landing_page
from corehq.apps.users.models import HqPermissions
from corehq.apps.users.models_role import UserRole, StaticRole
from corehq.apps.users.views import BaseRoleAccessView, _commcare_analytics_roles_options

from corehq.util.view_utils import json_error


class ListRolesView(BaseRoleAccessView):
    template_name = 'users/roles_and_permissions.html'
    page_title = gettext_lazy("Roles & Permissions")
    urlname = 'roles_and_permissions'

    @method_decorator(require_can_view_roles)
    def dispatch(self, request, *args, **kwargs):
        return super(ListRolesView, self).dispatch(request, *args, **kwargs)

    @property
    def can_edit_roles(self):
        return (has_privilege(self.request, privileges.ROLE_BASED_ACCESS)
                and self.couch_user.is_domain_admin)

    @property
    def landing_page_choices(self):
        return [
            {'id': None, 'name': _('Use Default')}
        ] + [
            {'id': page.id, 'name': _(page.name)}
            for page in get_allowed_landing_pages(self.domain)
        ]

    @property
    @memoized
    def non_admin_roles(self):
        return list(sorted(
            [role for role in UserRole.objects.get_by_domain(self.domain) if not role.is_commcare_user_default],
            key=lambda role: role.name if role.name else '\uFFFF'
        )) + [UserRole.commcare_user_default(self.domain)]  # mobile worker default listed last

    def can_edit_linked_roles(self):
        return self.request.couch_user.can_edit_linked_data(self.domain)

    def get_roles_for_display(self):
        show_es_issue = False
        role_view_data = [StaticRole.domain_admin(self.domain).to_json()]
        for role in self.non_admin_roles:
            role_data = role.to_json()
            role_view_data.append(role_data)

            if self.can_edit_roles:
                role_data["editUrl"] = reverse(EditRoleView.urlname,
                    kwargs={'domain': self.domain, 'role_id': role_data.get('_id')})

            if role.is_commcare_user_default:
                role_data["preventRoleDelete"] = True
            else:
                try:
                    user_count = get_role_user_count(role.domain, role.couch_id)
                    role_data["preventRoleDelete"] = bool(user_count)
                except TypeError:
                    # when query_result['hits'] returns None due to an ES issue
                    show_es_issue = True

            role_data["has_unpermitted_location_restriction"] = (
                not self.can_restrict_access_by_location
                and not role.permissions.access_all_locations
            )

        if show_es_issue:
            messages.error(
                self.request,
                mark_safe(_(  # nosec: no user input
                    "We might be experiencing issues fetching the entire list "
                    "of user roles right now. This issue is likely temporary and "
                    "nothing to worry about, but if you keep seeing this for "
                    "more than a day, please <a href='#modalReportIssue' "
                    "data-toggle='modal'>Report an Issue</a>."
                ))
            )
        return role_view_data

    def get_possible_profiles(self):
        from corehq.apps.users.views.mobile.custom_data_fields import (
            CUSTOM_USER_DATA_FIELD_TYPE,
        )
        definition = CustomDataFieldsDefinition.get(self.domain, CUSTOM_USER_DATA_FIELD_TYPE)
        if definition is not None:
            return [{
                    'id': profile.id,
                    'name': profile.name,
                    }
                for profile in definition.get_profiles()]
        else:
            return []

    @property
    def page_context(self):
        from corehq.apps.linked_domain.dbaccessors import is_active_downstream_domain
        if (not self.can_restrict_access_by_location
                and any(not role.permissions.access_all_locations
                        for role in self.non_admin_roles)):
            messages.warning(self.request, _(
                "This project has user roles that restrict data access by "
                "organization, but the software plan no longer supports that. "
                "Any users assigned to roles that are restricted in data access "
                "by organization can no longer access this project.  Please "
                "update the existing roles."))

        tableau_list = []
        if toggles.EMBEDDED_TABLEAU.enabled(self.domain):
            tableau_list = [{
                'id': viz.id,
                'name': viz.name,
            } for viz in TableauVisualization.objects.filter(domain=self.domain)]

        return {
            'is_managed_by_upstream_domain': is_active_downstream_domain(self.domain),
            'can_edit_linked_data': self.can_edit_linked_roles(),
            'user_roles': self.get_roles_for_display(),
            'non_admin_roles': self.non_admin_roles,
            'can_edit_roles': self.can_edit_roles,
            'default_role': StaticRole.domain_default(self.domain),
            'tableau_list': tableau_list,
            'report_list': get_possible_reports(self.domain),
            'profile_list': self.get_possible_profiles(),
            'is_domain_admin': self.couch_user.is_domain_admin,
            'domain_object': self.domain_object,
            'uses_locations': self.domain_object.uses_locations,
            'can_restrict_access_by_location': self.can_restrict_access_by_location,
            'landing_page_choices': self.landing_page_choices,
            'show_integration': (
                toggles.OPENMRS_INTEGRATION.enabled(self.domain)
                or toggles.DHIS2_INTEGRATION.enabled(self.domain)
                or toggles.GENERIC_INBOUND_API.enabled(self.domain)
            ),
            'web_apps_choices': get_cloudcare_apps(self.domain),
            'attendance_tracking_privilege': (
                toggles.ATTENDANCE_TRACKING.enabled(self.domain)
                and domain_has_privilege(self.domain, privileges.ATTENDANCE_TRACKING)
            ),
            'has_report_builder_access': has_report_builder_access(self.request),
            'data_file_download_enabled':
                domain_has_privilege(self.domain, privileges.DATA_FILE_DOWNLOAD),
            'export_ownership_enabled': domain_has_privilege(self.domain, privileges.EXPORT_OWNERSHIP),
            'data_registry_choices': get_data_registry_dropdown_options(self.domain),
            'commcare_analytics_roles': _commcare_analytics_roles_options(),
            'has_restricted_application_access': (
                get_application_access_for_domain(self.domain).restrict
                and toggles.WEB_APPS_PERMISSIONS_VIA_GROUPS.enabled(self.domain)
            ),
        }


# If any permission less than domain admin were allowed here, having that
# permission would give you the permission to change the permissions of your
# own role such that you could do anything, and would thus be equivalent to
# having domain admin permissions.
@json_error
@domain_admin_required
@require_POST
def post_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})
    role_data = json.loads(request.body.decode('utf-8'))

    try:
        role = _update_role_from_view(domain, role_data)
    except ValueError as e:
        return JsonResponse({
            "message": str(e)
        }, status=400)

    response_data = role.to_json()
    if role.is_commcare_user_default:
        response_data["preventRoleDelete"] = True
    else:
        user_count = get_role_user_count(domain, role.couch_id)
        response_data['preventRoleDelete'] = user_count > 0
    return JsonResponse(response_data)


def _update_role_from_view(domain, role_data):
    landing_page = role_data["default_landing_page"]
    if landing_page:
        validate_landing_page(domain, landing_page)

    if (
        not domain_has_privilege(domain, privileges.RESTRICT_ACCESS_BY_LOCATION)
        and not role_data['permissions']['access_all_locations']
    ):
        # This shouldn't be possible through the UI, but as a safeguard...
        role_data['permissions']['access_all_locations'] = True

    if "_id" in role_data:
        try:
            role = UserRole.objects.by_couch_id(role_data["_id"])
        except UserRole.DoesNotExist:
            role = UserRole()
        else:
            if role.domain != domain:
                raise Http404()
    else:
        role = UserRole()

    name = role_data["name"]
    if not role.id:
        if name.lower() == 'admin' or UserRole.objects.filter(domain=domain, name__iexact=name).exists():
            raise ValueError(_("A role with the same name already exists"))

    role.domain = domain
    role.name = name
    role.default_landing_page = landing_page
    role.is_non_admin_editable = role_data["is_non_admin_editable"]
    role.save()

    permissions = HqPermissions.wrap(role_data["permissions"])
    permissions.normalize(previous=role.permissions)
    role.set_permissions(permissions.to_list())

    assignable_by = role_data["assignable_by"]
    role.set_assignable_by_couch(assignable_by)
    return role


@domain_admin_required
@require_POST
def delete_user_role(request, domain):
    if not domain_has_privilege(domain, privileges.ROLE_BASED_ACCESS):
        return JsonResponse({})
    role_data = json.loads(request.body.decode('utf-8'))

    try:
        response_data = _delete_user_role(domain, role_data)
    except InvalidRequestException as e:
        return JsonResponse({"message": str(e)}, status=400)

    return JsonResponse(response_data)


def _delete_user_role(domain, role_data):
    try:
        role = UserRole.objects.by_couch_id(role_data["_id"], domain=domain)
    except UserRole.DoesNotExist:
        raise Http404

    if role.is_commcare_user_default:
        raise InvalidRequestException(_(
            "Unable to delete role '{role}'. "
            "This role is the default role for Mobile Users and can not be deleted.",
        ).format(role=role_data["name"]))

    user_count = get_role_user_count(domain, role_data["_id"])
    if user_count:
        raise InvalidRequestException(ngettext(
            "Unable to delete role '{role}'. "
            "It has one user and/or invitation still assigned to it. "
            "Remove all users assigned to the role before deleting it.",
            "Unable to delete role '{role}'. "
            "It has {user_count} users and/or invitations still assigned to it. "
            "Remove all users assigned to the role before deleting it.",
            user_count,
        ).format(role=role_data["name"], user_count=user_count))

    copy_id = role.couch_id
    role.delete()
    # return removed id in order to remove it from UI
    return {"_id": copy_id}


@method_decorator(use_bootstrap5, name='dispatch')
class EditRoleView(BaseRoleAccessView):
    urlname = "edit_role"
    template_name = 'users/edit_role.html'
    page_title = gettext_lazy("Edit Role")

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs={'domain': self.domain, 'role_id': self.kwargs.get('role_id')})

    @property
    def parent_pages(self):
        return [{
            'title': ListRolesView.page_title,
            'url': reverse(ListRolesView.urlname, args=[self.domain]),
        }]

    @property
    def page_context(self):
        role_data = self.role.to_json()
        role_data["accessAreas"] = [
            {
                "showOption": True,
                "editPermission": self.role.permissions.edit_web_users,
                "viewPermission": self.role.permissions.view_web_users,
                "text": _(
                    "<strong>Web Users</strong> &mdash; invite new web users, manage account settings, "
                    "remove membership"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-web-users-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-web-users-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Mobile Workers"),
                "screenReaderViewOnlyText": _("View-Only Mobile Workers"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": toggles.TABLEAU_USER_SYNCING.enabled(self.domain),
                "editPermission": self.role.permissions.edit_user_tableau_config,
                "viewPermission": self.role.permissions.view_user_tableau_config,
                "text": _(
                    "<strong>Manage Tableau Configuration</strong> &mdash; manage tableau configuration "
                    "for web users"),
                "showEditCheckbox": True,  # TODO: self.permissions.edit_web_users();
                "editCheckboxLabel": "edit-user-tableau-config-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-user-tableau-config-checkbox",
                "screenReaderEditAndViewText": _("Edit & View tableau configuration for web users"),
                "screenReaderViewOnlyText": _("View-Only tableau configuration for web users"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": True,
                "editPermission": self.role.permissions.edit_commcare_users,
                "viewPermission": self.role.permissions.view_commcare_users,
                "text": _(
                    "<strong>Mobile Workers</strong> &mdash; create new accounts, manage account settings, "
                    "deactivate or delete mobile workers."),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-commcare-users-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-commcare-users-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Web Users"),
                "screenReaderViewOnlyText": _("View-Only Web Users"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": self.role.permissions.access_all_locations,
                "editPermission": self.role.permissions.edit_groups,
                "viewPermission": self.role.permissions.view_groups,
                "text": _("<strong>Groups</strong> &mdash; manage groups of mobile workers"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-groups-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-groups-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Groups"),
                "screenReaderViewOnlyText": _("View-Only Web Groups"),
                "showAllowCheckbox": True,
                "allowCheckboxText": _("Allow changing group membership (requires edit groups)."),
                "allowCheckboxId": "edit-users-groups-checkbox",
                "allowCheckboxPermission": self.role.permissions.edit_users_in_groups,
            },
            {
                "showOption": True,
                "editPermission": self.role.permissions.edit_locations,
                "viewPermission": self.role.permissions.view_locations,
                "text": _("<strong>Locations</strong> &mdash; manage locations in the Organization's Hierarchy"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-locations-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-locations-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Locations"),
                "screenReaderViewOnlyText": _("View-Only Web Locations"),
                "showAllowCheckbox": True,
                "allowCheckboxText": _("Allow changing workers at a location."),
                "allowCheckboxId": "edit-users-locations-checkbox",
                "allowCheckboxPermission": self.role.permissions.edit_users_in_locations,
            },
            {
                "showOption": True,  # TODO: privileges.hasPrivilege('data_dictionary'),
                "editPermission": self.role.permissions.edit_data_dict,
                "viewPermission": self.role.permissions.view_data_dict,
                "text": _("<strong>Data Dictionary</strong> &mdash; manage case properties within CommCare HQ"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-data-dict-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-data-dict-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Data Dictionary"),
                "screenReaderViewOnlyText": _("View-Only Data Dictionary"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": True,
                "editPermission": self.role.permissions.edit_data,
                "viewPermission": False,
                "text": _("<strong>Data</strong> &mdash; view, export, and edit form and case data, "
                    "reassign cases"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-data-checkbox",
                "showViewCheckbox": False,
                "viewCheckboxLabel": "view-data-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Data"),
                "screenReaderViewOnlyText": None,
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": True,
                "editPermission": self.role.permissions.edit_messaging,
                "viewPermission": False,
                "text": _("<strong>Messaging</strong> &mdash; configure and send conditional alerts"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-messaging-checkbox",
                "showViewCheckbox": False,
                "viewCheckboxLabel": "view-messaging-checkbox",
                "screenReaderEditAndViewText": _("Access Messaging"),
                "screenReaderViewOnlyText": None,
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                # Since disabling "Full Organization Access" automatically disables "Access APIs"
                # and we never want "Access APIs" without "Full Organization Access",
                # we hide "Access APIs" when "Full Organization Access" is disabled.
                # If "Access APIs" is checked though, even if "Full Organization Access" isn't
                # we always want to show it.
                # One can no longer make this combination happen in the UI,
                # but for the small number of existing roles that have this combination
                # we want it to be displayed.
                # Unchecking "Access APIs" in this situation will then make the option disappear.
                "showOption": True,
                # TODO: self.permissions.access_all_locations() || self.permissions.access_api()
                "editPermission": self.role.permissions.access_api,
                "viewPermission": False,
                "text": _(
                    "<strong>Access APIs</strong> &mdash; use CommCare HQ APIs to read and update data. Specific "
                    "APIs may require additional permissions."),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-apis-checkbox",
                "showViewCheckbox": False,
                "viewCheckboxLabel": "view-apis-checkbox",
                "screenReaderEditAndViewText": _("Access APIs"),
                "screenReaderViewOnlyText": None,
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": self.role.permissions.access_all_locations,
                "editPermission": self.role.permissions.edit_apps,
                "viewPermission": self.role.permissions.view_apps,
                "text": _(
                    "<strong>Applications</strong> &mdash; modify or view the structure and configuration of "
                    "all applications."),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-apps-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-apps-checkbox",
                "screenReaderEditAndViewText": _("Edit & View Apps"),
                "screenReaderViewOnlyText": _("View-Only Applications"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": self.role.permissions.access_all_locations,
                "editPermission": False,
                "viewPermission": self.role.permissions.view_roles,
                "text": _(
                    "<strong>Roles &amp; Permissions</strong> &mdash; view web user and mobile worker roles &amp; "
                    "permissions (only Admins can edit roles)"),
                "showEditCheckbox": False,
                "editCheckboxLabel": "edit-roles-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-roles-checkbox",
                "screenReaderEditAndViewText": None,
                "screenReaderViewOnlyText": _("View Roles and Permissions"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            },
            {
                "showOption": True,  # TODO: root.DataFileDownloadEnabled
                "editPermission": self.role.permissions.edit_file_dropzone,
                "viewPermission": self.role.permissions.view_file_dropzone,
                "text": _("<strong>Dropzone</strong> &mdash; Upload and download files from the file Dropzone"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-dropzone-checkbox",
                "showViewCheckbox": True,
                "viewCheckboxLabel": "view-dropzone-checkbox",
                "screenReaderEditAndViewText": _("Edit & Download files from the Dropzone"),
                "screenReaderViewOnlyText": _("View-Only Dropzone"),
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            }, {
                "showOption": True,  # TODO: root.ExportOwnershipEnabled
                "editPermission": self.role.permissions.edit_shared_exports,
                "viewPermission": False,
                "text": _(
                    "<strong>Manage Shared Exports</strong> &mdash; access and edit the content and structure of "
                    "shared exports"),
                "showEditCheckbox": True,
                "editCheckboxLabel": "edit-shared-exports-checkbox",
                "showViewCheckbox": False,
                "viewCheckboxLabel": "view-shared-exports-checkbox",
                "screenReaderEditAndViewText": _("Manage Shared Exports"),
                "screenReaderViewOnlyText": None,
                "showAllowCheckbox": False,
                "allowCheckboxText": None,
                "allowCheckboxId": None,
                "allowCheckboxPermission": None,
            }
        ]
        return {
            "data": json.dumps(role_data)
        }

    @property
    def role(self):
        role_id = self.kwargs.get("role_id")
        try:
            return UserRole.objects.by_couch_id(role_id, self.domain)
        except UserRole.DoesNotExist:
            return None
