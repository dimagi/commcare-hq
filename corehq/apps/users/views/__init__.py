import json
from collections import defaultdict
from datetime import datetime
from django.conf import settings

import langcodes
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from couchdbkit.exceptions import ResourceNotFound
from crispy_forms.utils import render_crispy_form

from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps
from corehq.apps.registry.utils import get_data_registry_dropdown_options
from corehq.apps.reports.models import TableauVisualization, TableauUser
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.user_helpers import get_email_domain_from_username
from corehq.toggles import TABLEAU_USER_SYNCING

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
    HttpResponseBadRequest,
)
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, ngettext, gettext_lazy, gettext_noop

from corehq.apps.users.analytics import get_role_user_count
from soil.exceptions import TaskFailedError
from soil.util import expose_cached_download, get_download_context
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST
from django_digest.decorators import httpdigest
from django_prbac.utils import has_privilege
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import always_allow_project_access, requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import (
    HUBSPOT_INVITATION_SENT_FORM,
    send_hubspot_form,
    track_workflow,
)
from corehq.apps.app_manager.dbaccessors import get_app_languages
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    require_superuser,
)
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.es import UserES
from corehq.apps.hqwebapp.crispy import make_form_readonly
from corehq.apps.locations.permissions import (
    location_safe,
    user_can_access_other_user,
)
from corehq.apps.locations.models import SQLLocation
from corehq.apps.registration.forms import (
    AdminInvitesUserForm,
)
from corehq.apps.reports.exceptions import TableauAPIError
from corehq.apps.reports.util import get_possible_reports
from corehq.apps.sms.mixin import BadSMSConfigException
from corehq.apps.sms.verify import (
    VERIFICATION__ALREADY_IN_USE,
    VERIFICATION__ALREADY_VERIFIED,
    VERIFICATION__RESENT_PENDING,
    VERIFICATION__WORKFLOW_STARTED,
    initiate_sms_verification_workflow,
)
from corehq.apps.translations.models import SMSTranslations
from corehq.apps.userreports.util import has_report_builder_access
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.decorators import (
    can_use_filtered_user_download,
    require_can_edit_or_view_web_users,
    require_can_edit_web_users,
    require_can_view_roles,
    require_permission_to_edit_user,
)
from corehq.apps.users.exceptions import MissingRoleException, InvalidRequestException
from corehq.apps.users.forms import (
    BaseUserInfoForm,
    CommtrackUserForm,
    SetUserPasswordForm,
    UpdateUserRoleForm,
    TableauUserForm,
)
from corehq.apps.users.landing_pages import get_allowed_landing_pages, validate_landing_page
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DomainMembershipError,
    DomainRemovalRecord,
    DomainRequest,
    Invitation,
    StaticRole,
    WebUser,
    HqPermissions,
    UserRole,
)
from corehq.apps.users.util import log_user_change
from corehq.apps.users.views.utils import get_editable_role_choices, BulkUploadResponseWrapper
from corehq.apps.user_importer.importer import UserUploadError
from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.user_importer.tasks import import_users_and_groups, parallel_user_import
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.pillows.utils import WEB_USER_TYPE
from corehq.toggles import PARALLEL_USER_IMPORTS
from corehq.util.couch import get_document_or_404
from corehq.util.view_utils import json_error
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    WorksheetNotFound,
    get_workbook,
)

from dimagi.utils.logging import notify_exception


def _users_context(request, domain):
    couch_user = request.couch_user
    web_users = WebUser.by_domain(domain)

    for user in [couch_user] + list(web_users):
        user.current_domain = domain

    return {
        'web_users': web_users,
        'domain': domain,
        'couch_user': couch_user,
    }


class BaseUserSettingsView(BaseDomainView):
    section_name = gettext_noop("Users")

    @property
    @memoized
    def section_url(self):
        return reverse(DefaultProjectUserSettingsView.urlname, args=[self.domain])

    @property
    @memoized
    def couch_user(self):
        user = self.request.couch_user
        if user:
            user.current_domain = self.domain
        return user

    @property
    def main_context(self):
        context = super(BaseUserSettingsView, self).main_context
        context.update({
            'couch_user': self.couch_user,
        })
        return context


@method_decorator(always_allow_project_access, name='dispatch')
@location_safe
class DefaultProjectUserSettingsView(BaseUserSettingsView):
    urlname = "users_default"

    @property
    @memoized
    def redirect(self):
        redirect = None
        has_project_access = has_privilege(self.request, privileges.PROJECT_ACCESS)
        user = CouchUser.get_by_user_id(self.couch_user._id)
        if user:
            if ((user.has_permission(self.domain, 'edit_commcare_users')
                    or user.has_permission(self.domain, 'view_commcare_users'))
                    and has_project_access):
                from corehq.apps.users.views.mobile import MobileWorkerListView
                redirect = reverse(
                    MobileWorkerListView.urlname,
                    args=[self.domain]
                )

            elif ((user.has_permission(self.domain, 'edit_groups')
                    or user.has_permission(self.domain, 'view_groups'))
                    and has_project_access):
                from corehq.apps.users.views.mobile import GroupsListView
                redirect = reverse(
                    GroupsListView.urlname,
                    args=[self.domain]
                )

            elif (user.has_permission(self.domain, 'edit_web_users')
                    or user.has_permission(self.domain, 'view_web_users')):
                redirect = reverse(
                    ListWebUsersView.urlname,
                    args=[self.domain]
                )

            elif (user.has_permission(self.domain, 'view_roles')
                    and has_project_access):
                from corehq.apps.users.views import ListRolesView
                redirect = reverse(
                    ListRolesView.urlname,
                    args=[self.domain]
                )

            elif ((user.has_permission(self.domain, 'edit_locations')
                    or user.has_permission(self.domain, 'view_locations'))
                    and has_project_access):
                from corehq.apps.locations.views import LocationsListView
                redirect = reverse(
                    LocationsListView.urlname,
                    args=[self.domain]
                )

        return redirect

    def get(self, request, *args, **kwargs):
        if not self.redirect:
            raise Http404()
        return HttpResponseRedirect(self.redirect)


class BaseEditUserView(BaseUserSettingsView):

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain, self.editable_user_id])

    @property
    def parent_pages(self):
        return [{
            'title': ListWebUsersView.page_title,
            'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
        }]

    @property
    def editable_user_id(self):
        return self.kwargs.get('couch_user_id')

    @property
    @memoized
    def editable_user(self):
        try:
            return get_document_or_404(WebUser, self.domain, self.editable_user_id)
        except (ResourceNotFound, CouchUser.AccountTypeError):
            raise Http404()

    @property
    def existing_role(self):
        try:
            role = self.editable_user.get_role(self.domain)
        except DomainMembershipError:
            raise Http404()

        if role is None:
            if isinstance(self.editable_user, WebUser):
                raise MissingRoleException()
            return None
        else:
            return role.get_qualified_id()

    @property
    @memoized
    def editable_role_choices(self):
        return get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=False)

    @property
    def can_change_user_roles(self):
        return (
            bool(self.editable_role_choices)
            and self.request.couch_user.user_id != self.editable_user_id
            and (
                self.request.couch_user.is_domain_admin(self.domain)
                or not self.existing_role
                or self.existing_role
                in [choice[0] for choice in self.editable_role_choices]
            )
        )

    def form_user_update(self):
        raise NotImplementedError()

    @property
    def main_context(self):
        context = super(BaseEditUserView, self).main_context
        context.update({
            'couch_user': self.editable_user,
            'form_user_update': self.form_user_update,
            'phonenumbers': self.editable_user.phone_numbers_extended(self.request.couch_user),
        })
        return context

    @property
    @memoized
    def commtrack_form(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "commtrack":
            return CommtrackUserForm(self.request.POST, request=self.request, domain=self.domain)

        user_domain_membership = self.editable_user.get_domain_membership(self.domain)
        return CommtrackUserForm(
            domain=self.domain,
            request=self.request,
            initial={
                'primary_location': user_domain_membership.location_id,
                'program_id': user_domain_membership.program_id,
                'assigned_locations': user_domain_membership.assigned_location_ids,
            },
        )

    def update_user(self):
        if self.form_user_update.is_valid():
            return self.form_user_update.update_user()

    @property
    @memoized
    def tableau_form(self):
        try:
            if self.request.method == "POST" and self.request.POST['form_type'] == "tableau":
                return TableauUserForm(self.request.POST,
                                    request=self.request,
                                    domain=self.domain,
                                    username=self.editable_user.username)

            tableau_user = TableauUser.objects.filter(server__domain=self.domain).get(
                username=self.editable_user.username
            )
            return TableauUserForm(
                domain=self.domain,
                request=self.request,
                username=self.editable_user.username,
                initial={
                    'role': tableau_user.role
                }
            )
        except (TableauAPIError, TableauUser.DoesNotExist) as e:
            messages.error(self.request, _('''There was an error getting data for this user's associated Tableau
                                             user. Please contact support if this error persists.'''))
            notify_exception(self.request, str(e), details={
                'domain': self.domain,
                'exception_type': type(e),
            })

    def post(self, request, *args, **kwargs):
        saved = False
        if self.request.POST['form_type'] == "commtrack":
            if self.commtrack_form.is_valid():
                self.commtrack_form.save(self.editable_user)
                saved = True
        elif self.request.POST['form_type'] == "update-user":
            if self.update_user():
                messages.success(self.request, _('Changes saved for user "%s"') % self.editable_user.raw_username)
                saved = True
        elif self.request.POST['form_type'] == "tableau":
            if self.tableau_form and self.tableau_form.is_valid():
                self.tableau_form.save(self.editable_user.username)
                saved = True
        if saved:
            return HttpResponseRedirect(self.page_url)
        else:
            return self.get(request, *args, **kwargs)


class EditWebUserView(BaseEditUserView):
    template_name = "users/edit_web_user.html"
    urlname = "user_account"
    page_title = gettext_noop("Edit Web User")

    @property
    def page_name(self):
        if self.request.is_view_only:
            return _("Edit Web User (View Only)")
        return self.page_title

    @property
    @memoized
    def form_user_update(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "update-user":
            data = self.request.POST
        else:
            data = None
        form = UpdateUserRoleForm(data=data, domain=self.domain, existing_user=self.editable_user,
                                  request=self.request)

        if self.can_change_user_roles:
            try:
                existing_role = self.existing_role
            except MissingRoleException:
                existing_role = None
                messages.error(self.request, _("""
                    This user has no role. Please assign this user a role and save.
                """))
            form.load_roles(current_role=existing_role, role_choices=self.user_role_choices)
        else:
            del form.fields['role']

        return form

    @property
    def user_role_choices(self):
        role_choices = get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=True)
        try:
            self.existing_role
        except MissingRoleException:
            role_choices = [('none', _('(none)'))] + role_choices
        return role_choices

    @property
    @memoized
    def can_grant_superuser_access(self):
        return self.request.couch_user.is_superuser and toggles.SUPPORT.enabled(self.request.couch_user.username)

    @property
    def page_context(self):
        ctx = {
            'form_uneditable': BaseUserInfoForm(),
            'can_edit_role': self.can_change_user_roles,
        }
        if self.request.is_view_only:
            make_form_readonly(self.commtrack_form)
        if (
            self.request.project.commtrack_enabled
            or self.request.project.uses_locations
        ):
            ctx.update({'update_form': self.commtrack_form})
        if TABLEAU_USER_SYNCING.enabled(self.domain):
            ctx.update({'tableau_form': self.tableau_form})
        if self.can_grant_superuser_access:
            ctx.update({'update_permissions': True})

        idp = IdentityProvider.get_active_identity_provider_by_username(
            self.editable_user.username
        )
        ctx.update({
            'has_untrusted_identity_provider': (
                not IdentityProvider.does_domain_trust_user(
                    self.domain,
                    self.editable_user.username
                )
            ),
            'idp_name': idp.name if idp else '',
        })

        return ctx

    @method_decorator(always_allow_project_access)
    @method_decorator(require_can_edit_or_view_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(EditWebUserView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return super(EditWebUserView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.request.is_view_only:
            return self.get(request, *args, **kwargs)

        if self.request.POST['form_type'] == 'trust-identity-provider':
            idp = IdentityProvider.get_active_identity_provider_by_username(
                self.editable_user.username
            )
            if idp:
                idp.create_trust_with_domain(
                    self.domain,
                    self.request.user.username
                )
                messages.success(
                    self.request,
                    _('Your project space "{domain}" now trusts the SSO '
                      'Identity Provider "{idp_name}".').format(
                        domain=self.domain,
                        idp_name=idp.name,
                    )
                )

        return super(EditWebUserView, self).post(request, *args, **kwargs)


def get_domain_languages(domain):
    app_languages = get_app_languages(domain)
    translations = SMSTranslations.objects.filter(domain=domain).first()
    sms_languages = translations.langs if translations else []

    domain_languages = []
    for lang_code in app_languages.union(sms_languages):
        name = langcodes.get_name(lang_code)
        label = "{} ({})".format(lang_code, name) if name else lang_code
        domain_languages.append((lang_code, label))

    return sorted(domain_languages) or langcodes.get_all_langs_for_select()


class BaseRoleAccessView(BaseUserSettingsView):

    @property
    @memoized
    def can_restrict_access_by_location(self):
        return self.domain_object.has_privilege(
            privileges.RESTRICT_ACCESS_BY_LOCATION)

    @property
    @memoized
    def release_management_privilege(self):
        return self.domain_object.has_privilege(privileges.RELEASE_MANAGEMENT)

    @property
    @memoized
    def lite_release_management_privilege(self):
        """
        Only true if domain does not have privileges.RELEASE_MANAGEMENT
        """
        return self.domain_object.has_privilege(privileges.LITE_RELEASE_MANAGEMENT) and \
            not self.domain_object.has_privilege(privileges.RELEASE_MANAGEMENT)


@method_decorator(always_allow_project_access, name='dispatch')
@method_decorator(toggles.ENTERPRISE_USER_MANAGEMENT.required_decorator(), name='dispatch')
class EnterpriseUsersView(BaseRoleAccessView):
    template_name = 'users/enterprise_users.html'
    page_title = gettext_lazy("Enterprise Users")
    urlname = 'enterprise_users'

    @property
    def page_context(self):
        return {
            "show_profile_column": domain_has_privilege(self.domain, privileges.APP_USER_PROFILES),
        }


@method_decorator(always_allow_project_access, name='dispatch')
@method_decorator(require_can_edit_or_view_web_users, name='dispatch')
class ListWebUsersView(BaseRoleAccessView):
    template_name = 'users/web_users.html'
    page_title = gettext_lazy("Web Users")
    urlname = 'web_users'

    @property
    @memoized
    def role_labels(self):
        return {
            r.get_qualified_id(): r.name
            for r in [StaticRole.domain_admin(self.domain)] + UserRole.objects.get_by_domain(self.domain)
        }

    @property
    @memoized
    def invitations(self):
        return [
            {
                "uuid": str(invitation.uuid),
                "email": invitation.email,
                "email_marked_as_bounced": bool(invitation.email_marked_as_bounced),
                "invited_on": invitation.invited_on,
                "role_label": self.role_labels.get(invitation.role, ""),
                "email_status": invitation.email_status,
            }
            for invitation in Invitation.by_domain(self.domain)
        ]

    @property
    def page_context(self):
        from corehq.apps.users.views.mobile.users import FilteredWebUserDownload
        if can_use_filtered_user_download(self.domain):
            bulk_download_url = reverse(FilteredWebUserDownload.urlname, args=[self.domain])
        else:
            bulk_download_url = reverse("download_web_users", args=[self.domain])
        return {
            'invitations': self.invitations,
            'requests': DomainRequest.by_domain(self.domain) if self.request.couch_user.is_domain_admin else [],
            'admins': WebUser.get_admins_by_domain(self.domain),
            'domain_object': self.domain_object,
            'bulk_download_url': bulk_download_url,
            'from_address': settings.DEFAULT_FROM_EMAIL
        }


@require_can_edit_or_view_web_users
def download_web_users(request, domain):
    track_workflow(request.couch_user.get_email(), 'Bulk download web users selected')
    from corehq.apps.users.views.mobile.users import download_users
    return download_users(request, domain, user_type=WEB_USER_TYPE)


class DownloadWebUsersStatusView(BaseUserSettingsView):
    urlname = 'download_web_users_status'
    page_title = gettext_noop('Download Web Users Status')

    @method_decorator(require_can_edit_or_view_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': ListWebUsersView.page_title,
            'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
        }]

    def get(self, request, *args, **kwargs):
        context = super(DownloadWebUsersStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('user_download_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Download Web Users Status"),
            'progress_text': _("Preparing web user download."),
            'error_text': _("There was an unexpected error! Please try again or report an issue."),
            'next_url': reverse(ListWebUsersView.urlname, args=[self.domain]),
            'next_url_text': _("Go back to Web Users"),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


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
            'erm_privilege': self.release_management_privilege,
            'mrm_privilege': self.lite_release_management_privilege,
            'attendance_tracking_privilege': (
                toggles.ATTENDANCE_TRACKING.enabled(self.domain)
                and domain_has_privilege(self.domain, privileges.ATTENDANCE_TRACKING)
            ),
            'has_report_builder_access': has_report_builder_access(self.request),
            'data_file_download_enabled':
                domain_has_privilege(self.domain, privileges.DATA_FILE_DOWNLOAD),
            'export_ownership_enabled': domain_has_privilege(self.domain, privileges.EXPORT_OWNERSHIP),
            'data_registry_choices': get_data_registry_dropdown_options(self.domain),
        }


@always_allow_project_access
@require_can_edit_or_view_web_users
@require_GET
def paginate_enterprise_users(request, domain):
    # Get web users
    domains = [domain] + EnterprisePermissions.get_domains(domain)
    web_users, pagination = _get_web_users(request, domains)

    # Get linked mobile users
    web_user_usernames = [u.username for u in web_users]
    mobile_result = (
        UserES().show_inactive().domains(domains).mobile_users().sort('username.exact')
        .login_as_user(web_user_usernames)
        .run()
    )
    mobile_users = defaultdict(list)
    for hit in mobile_result.hits:
        login_as_user = {data['key']: data['value'] for data in hit['user_data_es']}.get('login_as_user')
        mobile_users[login_as_user].append(CommCareUser.wrap(hit))
    users = []
    allowed_domains = set(domains) - {domain}
    for web_user in web_users:
        loginAsUserCount = len(list(filter(lambda m: m['is_active'], mobile_users[web_user.username])))
        other_domains = [m.domain for m in web_user.domain_memberships if m.domain in allowed_domains]
        users.append({
            **_format_enterprise_user(domain, web_user),
            'otherDomains': other_domains,
            'loginAsUserCount': loginAsUserCount,
            'inactiveMobileCount': len(mobile_users[web_user.username]) - loginAsUserCount,
        })
        for mobile_user in sorted(mobile_users[web_user.username], key=lambda x: x.username):
            profile = mobile_user.get_user_data(domain).profile
            users.append({
                **_format_enterprise_user(mobile_user.domain, mobile_user),
                'profile': profile.name if profile else None,
                'otherDomains': [mobile_user.domain] if domain != mobile_user.domain else [],
                'loginAsUser': web_user.username,
                'is_active': mobile_user.is_active,
            })

    return JsonResponse({
        'users': users,
        **pagination,
    })


# user may be either a WebUser or a CommCareUser
def _format_enterprise_user(domain, user):
    membership = user.get_domain_membership(domain)
    role = membership.role if membership else None
    return {
        'username': user.raw_username,
        'name': user.full_name,
        'id': user.get_id,
        'role': role.name if role else None,
    }


@always_allow_project_access
@require_can_edit_or_view_web_users
@require_GET
def paginate_web_users(request, domain):
    web_users, pagination = _get_web_users(request, [domain])
    web_users_fmt = [{
        'eulas': u.get_eulas(),
        'email': u.get_email(),
        'domain': domain,
        'name': u.full_name,
        'role': u.role_label(domain),
        'phoneNumbers': u.phone_numbers,
        'id': u.get_id,
        'editUrl': reverse('user_account', args=[domain, u.get_id]),
        'removeUrl': (
            reverse('remove_web_user', args=[domain, u.user_id])
            if request.user.username != u.username else None
        ),
        'isUntrustedIdentityProvider': not IdentityProvider.does_domain_trust_user(
            domain, u.username
        ),
    } for u in web_users]

    return JsonResponse({
        'users': web_users_fmt,
        **pagination,
    })


def _get_web_users(request, domains):
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    skip = limit * (page - 1)
    query = request.GET.get('query')

    result = (
        UserES().domains(domains).web_users().sort('username.exact')
        .search_string_query(query, ["username", "last_name", "first_name"])
        .start(skip).size(limit).run()
    )

    return (
        [WebUser.wrap(w) for w in result.hits],
        {
            'total': result.total,
            'page': page,
            'query': query,
        },
    )


@always_allow_project_access
@require_can_edit_web_users
@require_POST
def remove_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    # if no user, very likely they just pressed delete twice in rapid succession so
    # don't bother doing anything.
    if user:
        record = user.delete_domain_membership(domain, create_record=True)
        user.save()
        # web user's membership is bound to the domain, so log as a change for that domain
        log_user_change(by_domain=request.domain, for_domain=domain, couch_user=user,
                        changed_by_user=request.couch_user, changed_via=USER_CHANGE_VIA_WEB,
                        change_messages=UserChangeMessage.domain_removal(domain))
        if record:
            message = _('You have successfully removed {username} from your '
                        'project space. <a href="{url}" class="post-link">Undo</a>')
            messages.success(request, message.format(
                username=user.username,
                url=reverse('undo_remove_web_user', args=[domain, record.get_id])
            ), extra_tags="html")
        else:
            message = _('It appears {username} has already been removed from your project space.')
            messages.success(request, message.format(username=user.username))

    return HttpResponseRedirect(
        reverse(ListWebUsersView.urlname, args=[domain]))


@always_allow_project_access
@require_can_edit_web_users
def undo_remove_web_user(request, domain, record_id):
    record = DomainRemovalRecord.get(record_id)
    record.undo()
    messages.success(request, 'You have successfully restored {username}.'.format(
        username=WebUser.get_by_user_id(record.user_id).username
    ))

    return HttpResponseRedirect(
        reverse(ListWebUsersView.urlname, args=[domain]))


# If any permission less than domain admin were allowed here, having that permission would give you the permission
# to change the permissions of your own role such that you could do anything, and would thus be equivalent to
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


@always_allow_project_access
@require_POST
@require_can_edit_web_users
def delete_request(request, domain):
    DomainRequest.objects.get(id=request.POST['id']).delete()
    return JsonResponse({'status': 'ok'})


@always_allow_project_access
@require_POST
@require_can_edit_web_users
def check_sso_trust(request, domain):
    username = request.POST['username']
    is_trusted = IdentityProvider.does_domain_trust_user(domain, username)
    response = {
        'is_trusted': is_trusted,
    }
    if not is_trusted:
        response.update({
            'email_domain': get_email_domain_from_username(username),
            'idp_name': IdentityProvider.get_active_identity_provider_by_username(
                username
            ).name,
        })
    return JsonResponse(response)


class BaseManageWebUserView(BaseUserSettingsView):

    @method_decorator(always_allow_project_access)
    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseManageWebUserView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': ListWebUsersView.page_title,
            'url': reverse(ListWebUsersView.urlname, args=[self.domain]),
        }]


class InviteWebUserView(BaseManageWebUserView):
    template_name = "users/invite_web_user.html"
    urlname = 'invite_web_user'
    page_title = gettext_lazy("Invite Web User to Project")

    @property
    @memoized
    def invite_web_user_form(self):
        role_choices = get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=True)
        loc = None
        domain_request = DomainRequest.objects.get(id=self.request_id) if self.request_id else None
        is_add_user = self.request_id is not None
        initial = {
            'email': domain_request.email if domain_request else None,
        }
        if 'location_id' in self.request.GET:
            from corehq.apps.locations.models import SQLLocation
            loc = SQLLocation.objects.get(location_id=self.request.GET.get('location_id'))
        if self.request.method == 'POST':
            current_users = [user.username for user in WebUser.by_domain(self.domain)]
            pending_invites = [di.email for di in Invitation.by_domain(self.domain)]
            return AdminInvitesUserForm(
                self.request.POST,
                excluded_emails=current_users + pending_invites,
                role_choices=role_choices,
                domain=self.domain,
                is_add_user=is_add_user,
            )
        return AdminInvitesUserForm(
            initial=initial,
            role_choices=role_choices,
            domain=self.domain,
            location=loc,
            is_add_user=is_add_user,
        )

    @property
    @memoized
    def request_id(self):
        if 'request_id' in self.request.GET:
            return self.request.GET.get('request_id')
        return None

    @property
    def page_context(self):
        return {
            'registration_form': self.invite_web_user_form,
        }

    def post(self, request, *args, **kwargs):
        if self.invite_web_user_form.is_valid():
            # If user exists and has already requested access, just add them to the project
            # Otherwise, send an invitation
            create_invitation = True
            data = self.invite_web_user_form.cleaned_data
            domain_request = DomainRequest.by_email(self.domain, data["email"])
            if domain_request is not None:
                domain_request.is_approved = True
                domain_request.save()
                user = CouchUser.get_by_username(domain_request.email)
                if user is not None:
                    domain_request.send_approval_email()
                    create_invitation = False
                    user.add_as_web_user(self.domain, role=data["role"],
                                         location_id=data.get("supply_point", None),
                                         program_id=data.get("program", None))
                messages.success(request, "%s added." % data["email"])
            else:
                track_workflow(request.couch_user.get_email(),
                               "Sent a project invitation",
                               {"Sent a project invitation": "yes"})
                send_hubspot_form(HUBSPOT_INVITATION_SENT_FORM, request)
                messages.success(request, "Invitation sent to %s" % data["email"])

            if create_invitation:
                data["invited_by"] = request.couch_user.user_id
                data["invited_on"] = datetime.utcnow()
                data["domain"] = self.domain
                # Preparation for location to replace supply_point
                supply_point = data.get("supply_point", None)
                data["location"] = SQLLocation.by_location_id(supply_point) if supply_point else None
                invite = Invitation(**data)
                invite.save()
                invite.send_activation_email()

            # Ensure trust is established with Invited User's Identity Provider
            if not IdentityProvider.does_domain_trust_user(self.domain, data["email"]):
                idp = IdentityProvider.get_active_identity_provider_by_username(data["email"])
                idp.create_trust_with_domain(self.domain, self.request.user.username)

            return HttpResponseRedirect(reverse(
                ListWebUsersView.urlname,
                args=[self.domain]
            ))
        return self.get(request, *args, **kwargs)


class BaseUploadUser(BaseUserSettingsView):
    def post(self, request, *args, **kwargs):
        """View's dispatch method automatically calls this"""
        try:
            self.workbook = get_workbook(request.FILES.get('bulk_upload_file'))
        except WorkbookJSONError as e:
            messages.error(request, str(e))
            return self.get(request, *args, **kwargs)

        try:
            self.user_specs = self.workbook.get_worksheet(title='users')
        except WorksheetNotFound:
            try:
                self.user_specs = self.workbook.get_worksheet()
            except WorksheetNotFound:
                return HttpResponseBadRequest("Workbook has no worksheets")

        try:
            self.group_specs = self.workbook.get_worksheet(title='groups')
        except WorksheetNotFound:
            self.group_specs = []
        try:
            from corehq.apps.user_importer.importer import check_headers
            check_headers(self.user_specs, self.domain, is_web_upload=self.is_web_upload)
        except UserUploadError as e:
            messages.error(request, _(str(e)))
            return HttpResponseRedirect(reverse(self.urlname, args=[self.domain]))

        task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)
        if PARALLEL_USER_IMPORTS.enabled(self.domain) and not self.is_web_upload:
            if list(self.group_specs):
                messages.error(
                    request,
                    _("Groups are not allowed with parallel user import. Please upload them separately")
                )
                return HttpResponseRedirect(reverse(self.urlname, args=[self.domain]))

            task = parallel_user_import.delay(
                self.domain,
                list(self.user_specs),
                request.couch_user.user_id
            )
        else:
            upload_record = UserUploadRecord(
                domain=self.domain,
                user_id=request.couch_user.user_id
            )
            upload_record.save()
            task = import_users_and_groups.delay(
                self.domain,
                list(self.user_specs),
                list(self.group_specs),
                request.couch_user.user_id,
                upload_record.pk,
                self.is_web_upload
            )
        task_ref.set_task(task)
        if self.is_web_upload:
            return HttpResponseRedirect(
                reverse(
                    WebUserUploadStatusView.urlname,
                    args=[self.domain, task_ref.download_id]
                )
            )
        else:
            from corehq.apps.users.views.mobile import UserUploadStatusView
            return HttpResponseRedirect(
                reverse(
                    UserUploadStatusView.urlname,
                    args=[self.domain, task_ref.download_id]
                )
            )


class UploadWebUsers(BaseUploadUser):
    template_name = 'hqwebapp/bulk_upload.html'
    urlname = 'upload_web_users'
    page_title = gettext_noop("Bulk Upload Web Users")
    is_web_upload = True

    @method_decorator(always_allow_project_access)
    @method_decorator(require_can_edit_web_users)
    @method_decorator(requires_privilege_with_fallback(privileges.BULK_USER_MANAGEMENT))
    def dispatch(self, request, *args, **kwargs):
        return super(UploadWebUsers, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        request_params = self.request.GET if self.request.method == 'GET' else self.request.POST
        from corehq.apps.users.views.mobile import get_user_upload_context
        return get_user_upload_context(self.domain, request_params, "download_web_users", "web user", "web users")

    def post(self, request, *args, **kwargs):
        track_workflow(request.couch_user.get_email(), 'Bulk upload web users selected')
        return super(UploadWebUsers, self).post(request, *args, **kwargs)


class WebUserUploadStatusView(BaseManageWebUserView):
    urlname = 'web_user_upload_status'
    page_title = gettext_noop('Web User Upload Status')

    def get(self, request, *args, **kwargs):
        context = super(WebUserUploadStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse(WebUserUploadJobPollView.urlname, args=[self.domain, kwargs['download_id']]),
            'title': _("Web User Upload Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
            'next_url': reverse(ListWebUsersView.urlname, args=[self.domain]),
            'next_url_text': _("Return to manage web users"),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class UserUploadJobPollView(BaseUserSettingsView):

    def get(self, request, domain, download_id):
        try:
            context = get_download_context(download_id)
        except TaskFailedError:
            return HttpResponseServerError()

        context.update({
            'on_complete_short': _('Bulk upload complete.'),
            'on_complete_long': _(self.on_complete_long),
            'user_type': _(self.user_type),
        })

        context['result'] = BulkUploadResponseWrapper(context)
        return render(request, 'users/mobile/partials/user_upload_status.html', context)


class WebUserUploadJobPollView(UserUploadJobPollView, BaseManageWebUserView):
    urlname = "web_user_upload_job_poll"
    on_complete_long = 'Web Worker upload has finished'
    user_type = 'web users'

    @method_decorator(require_can_edit_web_users)
    def dispatch(self, request, *args, **kwargs):
        return super(WebUserUploadJobPollView, self).dispatch(request, *args, **kwargs)


@require_POST
@always_allow_project_access
@require_permission_to_edit_user
def make_phone_number_default(request, domain, couch_user_id):
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not user.is_current_web_user(request) and not user.is_commcare_user():
        raise Http404()

    phone_number = request.POST['phone_number']
    if not phone_number:
        raise Http404('Must include phone number in request.')

    user.set_default_phone_number(phone_number)
    from corehq.apps.users.views.mobile import EditCommCareUserView
    redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    return HttpResponseRedirect(redirect)


@require_POST
@always_allow_project_access
@require_permission_to_edit_user
def delete_phone_number(request, domain, couch_user_id):
    user = CouchUser.get_by_user_id(couch_user_id, domain)
    if not user.is_current_web_user(request) and not user.is_commcare_user():
        raise Http404()

    phone_number = request.POST['phone_number']
    if not phone_number:
        raise Http404('Must include phone number in request.')

    user.delete_phone_number(phone_number)
    log_user_change(
        by_domain=request.domain,
        for_domain=user.domain,
        couch_user=user,
        changed_by_user=request.couch_user,
        changed_via=USER_CHANGE_VIA_WEB,
        change_messages=UserChangeMessage.phone_numbers_removed([phone_number])
    )
    from corehq.apps.users.views.mobile import EditCommCareUserView
    redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    return HttpResponseRedirect(redirect)


@always_allow_project_access
@require_permission_to_edit_user
def verify_phone_number(request, domain, couch_user_id):
    """
    phone_number cannot be passed in the url due to special characters
    but it can be passed as %-encoded GET parameters
    """
    if 'phone_number' not in request.GET:
        raise Http404('Must include phone number in request.')
    phone_number = six.moves.urllib.parse.unquote(request.GET['phone_number'])
    user = CouchUser.get_by_user_id(couch_user_id, domain)

    try:
        result = initiate_sms_verification_workflow(user, phone_number)
    except BadSMSConfigException as error:
        messages.error(request, _('Bad SMS configuration: {error}').format(error=error))
    else:
        if result == VERIFICATION__ALREADY_IN_USE:
            messages.error(request, _('Cannot start verification workflow. Phone number is already in use.'))
        elif result == VERIFICATION__ALREADY_VERIFIED:
            messages.error(request, _('Phone number is already verified.'))
        elif result == VERIFICATION__RESENT_PENDING:
            messages.success(request, _('Verification message resent.'))
        elif result == VERIFICATION__WORKFLOW_STARTED:
            messages.success(request, _('Verification workflow started.'))

    from corehq.apps.users.views.mobile import EditCommCareUserView
    redirect = reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id])
    return HttpResponseRedirect(redirect)


@always_allow_project_access
@require_superuser
@login_and_domain_required
def domain_accounts(request, domain, couch_user_id, template="users/domain_accounts.html"):
    context = _users_context(request, domain)
    couch_user = WebUser.get_by_user_id(couch_user_id, domain)
    if request.method == "POST" and 'domain' in request.POST:
        domain = request.POST['domain']
        couch_user.add_domain_membership(domain)
        couch_user.save()
        messages.success(request, 'Domain added')
    context.update({"user": request.user})
    return render(request, template, context)


@always_allow_project_access
@require_POST
@require_superuser
def add_domain_membership(request, domain, couch_user_id, domain_name):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    if domain_name:
        user.add_domain_membership(domain_name)
        user.save()
    return HttpResponseRedirect(reverse("user_account", args=(domain, couch_user_id)))


@always_allow_project_access
@sensitive_post_parameters('new_password1', 'new_password2')
@login_and_domain_required
@location_safe
def change_password(request, domain, login_id):
    # copied from auth's password_change

    commcare_user = CommCareUser.get_by_user_id(login_id, domain)
    json_dump = {}
    if not commcare_user or not user_can_access_other_user(domain, request.couch_user, commcare_user):
        raise Http404()
    django_user = commcare_user.get_django_user()
    if request.method == "POST":
        form = SetUserPasswordForm(request.project, login_id, user=django_user, data=request.POST)
        input = request.POST['new_password1']
        if input == request.POST['new_password2']:
            if form.project.strong_mobile_passwords:
                try:
                    clean_password(input)
                except ValidationError:
                    json_dump['status'] = 'weak'
            if form.is_valid():
                form.save()
                log_user_change(
                    by_domain=domain,
                    for_domain=commcare_user.domain,
                    couch_user=commcare_user,
                    changed_by_user=request.couch_user,
                    changed_via=USER_CHANGE_VIA_WEB,
                    change_messages=UserChangeMessage.password_reset()
                )
                json_dump['status'] = 'OK'
                form = SetUserPasswordForm(request.project, login_id, user='')
        else:
            json_dump['status'] = 'different'
    else:
        form = SetUserPasswordForm(request.project, login_id, user=django_user)
    json_dump['formHTML'] = render_crispy_form(form)
    return HttpResponse(json.dumps(json_dump))


@httpdigest
@login_and_domain_required
def test_httpdigest(request, domain):
    return HttpResponse("ok")


@always_allow_project_access
@csrf_exempt
@require_POST
@require_superuser
def register_fcm_device_token(request, domain, couch_user_id, device_token):
    user = WebUser.get_by_user_id(couch_user_id)
    user.fcm_device_token = device_token
    user.save()
    return HttpResponse()
