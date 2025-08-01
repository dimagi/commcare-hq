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

from corehq.apps.cloudcare.dbaccessors import get_cloudcare_apps, get_application_access_for_domain
from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.models import CustomDataFieldsProfile, CustomDataFieldsDefinition, PROFILE_SLUG
from corehq.apps.programs.models import Program
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
from django.utils.functional import cached_property
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
    track_workflow_noop,
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
    TableauUserForm,
    WebUserFormSet,
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
from corehq.apps.users.model_log import InviteModelAction
from corehq.apps.users.util import log_user_change
from corehq.apps.users.views.utils import (
    filter_user_query_by_locations_accessible_to_user,
    get_editable_role_choices, BulkUploadResponseWrapper,
    user_can_access_invite
)
from corehq.apps.user_importer.importer import UserUploadError
from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.user_importer.tasks import import_users_and_groups, parallel_user_import
from corehq.const import USER_CHANGE_VIA_WEB, INVITATION_CHANGE_VIA_WEB
from corehq.pillows.utils import WEB_USER_TYPE
from corehq.toggles import PARALLEL_USER_IMPORTS
from corehq.util.couch import get_document_or_404
from corehq.util.view_utils import json_error
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    WorksheetNotFound,
    get_workbook,
)
from corehq.apps.users.permissions import (
    COMMCARE_ANALYTICS_SQL_LAB,
    COMMCARE_ANALYTICS_DATASET_EDITOR,
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
                or self.existing_role in [choice[0] for choice in self.editable_role_choices]
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
        user = CouchUser.get_by_user_id(self.couch_user._id)
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
                },
                readonly=(not user.has_permission(self.domain, 'edit_user_tableau_config'))
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
                saved = True
        elif self.request.POST['form_type'] == "tableau":
            if self.tableau_form and self.tableau_form.is_valid():
                self.tableau_form.save(self.editable_user.username)
                saved = True
        if saved:
            messages.success(self.request, _('Changes saved for user "%s"') % self.editable_user.raw_username)
            return HttpResponseRedirect(self.page_url)
        else:
            return self.get(request, *args, **kwargs)

    def dispatch(self, *args, **kwargs):
        if not user_can_access_other_user(self.domain, self.request.couch_user, self.editable_user):
            return HttpResponse(status=401)
        return super().dispatch(*args, **kwargs)


@location_safe
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
        form = WebUserFormSet(data=data, domain=self.domain,
            editable_user=self.editable_user, request_user=self.request.couch_user, request=self.request)

        if self.can_change_user_roles:
            try:
                existing_role = self.existing_role
            except MissingRoleException:
                existing_role = None
                messages.error(self.request, _("""
                    This user has no role. Please assign this user a role and save.
                """))
            form.user_form.load_roles(current_role=existing_role, role_choices=self.user_role_choices)
        else:
            del form.user_form.fields['role']

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
            'user_data': self.editable_user.get_user_data(self.domain).to_dict(),
            'can_access_all_locations': self.request.couch_user.has_permission(
                self.domain, 'access_all_locations'
            ),
            'editable_user_can_access_all_locations': self.editable_user.has_permission(
                self.domain, 'access_all_locations'
            )
        }

        original_profile_id = self.editable_user.get_user_data(self.domain).profile_id
        field_view_context = self.form_user_update.custom_data.field_view.get_field_page_context(
            self.domain, self.request.couch_user, self.form_user_update.custom_data, original_profile_id
        )
        ctx.update(field_view_context)
        if self.request.is_view_only:
            make_form_readonly(self.commtrack_form)
        if self.request.project.commtrack_enabled or self.request.project.uses_locations:
            ctx.update({'update_form': self.commtrack_form})
        if TABLEAU_USER_SYNCING.enabled(self.domain):
            user = CouchUser.get_by_user_id(self.couch_user._id)
            ctx.update({
                'tableau_form': self.tableau_form,
                'view_user_tableau_config': user.has_permission(self.domain, 'view_user_tableau_config'),
                'edit_user_tableau_config': user.has_permission(self.domain, 'edit_user_tableau_config')
            })
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
        if toggles.SUPPORT.enabled(self.request.couch_user.username):
            ctx["support_info"] = {
                'locations': self.editable_user.get_sql_locations(self.domain)
            }
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


@method_decorator(always_allow_project_access, name='dispatch')
@method_decorator(require_can_edit_or_view_web_users, name='dispatch')
@location_safe
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
        invitations = Invitation.by_domain(self.domain)
        if not self.request.couch_user.has_permission(self.domain, 'access_all_locations'):
            invitations = [invite for invite in invitations if user_can_access_invite(
                self.domain, self.request.couch_user, invite)]
        return [
            {
                "uuid": str(invitation.uuid),
                "email": invitation.email,
                "email_marked_as_bounced": bool(invitation.email_marked_as_bounced),
                "invited_on": invitation.invited_on,
                "role_label": self.role_labels.get(invitation.role, ""),
                "email_status": invitation.email_status,
            }
            for invitation in invitations
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
@location_safe
def download_web_users(request, domain):
    track_workflow_noop(request.couch_user.get_email(), 'Bulk download web users selected')
    from corehq.apps.users.views.mobile.users import download_users
    return download_users(request, domain, user_type=WEB_USER_TYPE)


@location_safe
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


def _commcare_analytics_roles_options():
    return [
        {
            'slug': COMMCARE_ANALYTICS_SQL_LAB,
            'name': 'SQL Lab'
        },
        {
            'slug': COMMCARE_ANALYTICS_DATASET_EDITOR,
            'name': 'Dataset Editor'
        }
    ]


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
        UserES().domain(domains, include_inactive=True).mobile_users().sort('username.exact')
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
@location_safe
def paginate_web_users(request, domain):
    web_users, pagination = _get_web_users(request, [domain], filter_by_accessible_locations=True)
    web_users_fmt = []
    for u in web_users:
        user = {
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
            'deactivateUrl': '',
            'reactivateUrl': '',
        }
        # Omit option to deactivate/reactivate for a domain if user access is controlled by an IdentityProvider
        if (IdentityProvider.get_required_identity_provider(u.username) is None
                and toggles.DEACTIVATE_WEB_USERS.enabled(domain)):
            if u.is_active_in_domain(domain):
                user.update({
                    'deactivateUrl': (
                        reverse('deactivate_web_user', args=[domain, u.user_id])
                        if request.user.username != u.username else None
                    ),
                })
            else:
                user.update({
                    'reactivateUrl': (
                        reverse('reactivate_web_user', args=[domain, u.user_id])
                        if request.user.username != u.username else None
                    ),
                })
        web_users_fmt.append(user)

    return JsonResponse({
        'users': web_users_fmt,
        **pagination,
    })


def _get_web_users(request, domains, filter_by_accessible_locations=False):
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    skip = limit * (page - 1)
    query = request.GET.get('query')
    active_in_domain = json.loads(request.GET.get('showActiveUsers', None))

    user_es = UserES()
    if active_in_domain is None:
        user_es = user_es.domain(domains)
    else:
        user_es = user_es.domain(domains, include_active=active_in_domain, include_inactive=not active_in_domain)
        assert len(domains) == 1

    user_es = (
        user_es
        .web_users().sort('username.exact')
        .search_string_query(query, ["username", "last_name", "first_name"])
        .start(skip).size(limit)
    )
    if filter_by_accessible_locations:
        assert len(domains) == 1
        domain = domains[0]
        user_es = filter_user_query_by_locations_accessible_to_user(user_es, domain, request.couch_user)
    result = user_es.run()

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
@location_safe
def remove_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    # if no user, very likely they just pressed delete twice in rapid succession so
    # don't bother doing anything.
    if user:
        if not user_can_access_other_user(domain, request.couch_user, user):
            return HttpResponse(status=401)
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


@always_allow_project_access
@require_can_edit_web_users
@toggles.DEACTIVATE_WEB_USERS.required_decorator()
@require_POST
@location_safe
def deactivate_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    if user:
        if not user_can_access_other_user(domain, request.couch_user, user):
            return HttpResponse(status=401)
        user.deactivate(domain, changed_by=request.couch_user)
        messages.success(request, 'You have successfully deactivated {username}.'.format(username=user.username))
    return HttpResponseRedirect(reverse(ListWebUsersView.urlname, args=[domain]))


@always_allow_project_access
@require_can_edit_web_users
@toggles.DEACTIVATE_WEB_USERS.required_decorator()
@require_POST
@location_safe
def reactivate_web_user(request, domain, couch_user_id):
    user = WebUser.get_by_user_id(couch_user_id, domain)
    if user:
        if not user_can_access_other_user(domain, request.couch_user, user):
            return HttpResponse(status=401)
        user.reactivate(domain, changed_by=request.couch_user)
        messages.success(request, 'You have successfully reactivated {username}.'.format(username=user.username))
    return HttpResponseRedirect(reverse(ListWebUsersView.urlname, args=[domain]))


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


@always_allow_project_access
@require_POST
@require_can_edit_web_users
def delete_request(request, domain):
    DomainRequest.objects.get(id=request.POST['id']).delete()
    return JsonResponse({'status': 'ok'})


@always_allow_project_access
@require_POST
@require_can_edit_web_users
@location_safe
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


@location_safe
class InviteWebUserView(BaseManageWebUserView):
    template_name = "users/invite_web_user.html"
    urlname = 'invite_web_user'
    page_title = gettext_lazy("Invite Web User to Project")

    @property
    @memoized
    def invite_web_user_form(self):
        role_choices = get_editable_role_choices(self.domain, self.request.couch_user, allow_admin_role=True)
        domain_request = DomainRequest.objects.get(id=self.request_id) if self.request_id else None
        is_add_user = self.request_id is not None
        invitation = self.invitation
        if invitation:
            assigned_location_ids = list(invitation.assigned_locations.all().values_list('location_id', flat=True))
            primary_location_id = getattr(invitation.primary_location, "location_id", None)
            initial = {
                'email': invitation.email,
                'role': invitation.role,
                'assigned_locations': assigned_location_ids,
                'primary_location': primary_location_id,
            }
        else:
            initial = {
                'email': domain_request.email if domain_request else None,
            }
        can_edit_tableau_config = (self.request.couch_user.has_permission(self.domain, 'edit_user_tableau_config')
                                and toggles.TABLEAU_USER_SYNCING.enabled(self.domain))
        if self.request.method == 'POST':
            return AdminInvitesUserForm(
                self.request.POST,
                role_choices=role_choices,
                domain=self.domain,
                is_add_user=is_add_user,
                should_show_location=self.request.project.uses_locations,
                can_edit_tableau_config=can_edit_tableau_config,
                request=self.request,
                custom_data=self.custom_data,
                invitation=invitation
            )
        return AdminInvitesUserForm(
            initial=initial,
            role_choices=role_choices,
            domain=self.domain,
            is_add_user=is_add_user,
            should_show_location=self.request.project.uses_locations,
            can_edit_tableau_config=can_edit_tableau_config,
            request=self.request,
            custom_data=self.custom_data,
            invitation=invitation
        )

    @cached_property
    def custom_data(self):
        from corehq.apps.users.views.mobile.custom_data_fields import WebUserFieldsView
        post_dict = None
        if self.request.method == 'POST':
            post_dict = self.request.POST
        custom_data = CustomDataEditor(
            field_view=WebUserFieldsView,
            domain=self.domain,
            post_dict=post_dict,
            ko_model="custom_fields",
            request_user=self.request.couch_user
        )
        return custom_data

    @property
    @memoized
    def request_id(self):
        if 'request_id' in self.request.GET:
            return self.request.GET.get('request_id')
        return None

    @property
    def page_context(self):
        initial_values = {}
        if self.invitation:
            initial_values = {f.slug: self.invitation.custom_user_data.get(f.slug)
                              for f in self.custom_data.fields}
            if self.invitation.profile:
                initial_values[PROFILE_SLUG] = self.invitation.profile.id
        ctx = {
            'registration_form': self.invite_web_user_form,
            'user_data': initial_values,
            **self.custom_data.field_view.get_field_page_context(
                self.domain, self.request.couch_user, self.custom_data, None
            )
        }
        return ctx

    def _assert_user_has_permission_to_access_locations(self, assigned_location_ids):
        if not set(assigned_location_ids).issubset(set(SQLLocation.objects.accessible_to_user(
                self.domain, self.request.couch_user).values_list('location_id', flat=True))):
            raise Http404()

    @property
    def invitation(self):
        invitation_id = self.kwargs.get("invitation_id")
        try:
            return Invitation.objects.get(uuid=invitation_id)
        except Invitation.DoesNotExist:
            return None

    def post(self, request, *args, **kwargs):
        if self.invite_web_user_form.is_valid():
            # If user exists and has already requested access, just add them to the project
            # Otherwise, send an invitation
            create_invitation = True
            data = self.invite_web_user_form.cleaned_data
            domain_request = DomainRequest.by_email(self.domain, data["email"])
            profile_id = data.get("profile", None)
            profile = CustomDataFieldsProfile.objects.get(
                id=profile_id,
                definition__domain=self.domain) if profile_id else None
            user = CouchUser.get_by_username(data["email"])
            invitation = self.invitation
            if invitation:
                create_invitation = False
                invitation, changed_values = self._get_and_set_changes(invitation, data, profile)
                changes = self.format_changes(self.domain, changed_values)
                user_data = data.get("custom_user_data", {})
                changed_user_data = {}
                for key, value in invitation.custom_user_data.items():
                    if key in user_data and user_data[key] != value:
                        changed_user_data[key] = user_data[key]
                changes.update({"custom_user_data": changed_user_data})
                invitation.custom_user_data = user_data
                invitation.save(logging_values={"changed_by": request.couch_user.user_id,
                                                "changed_via": INVITATION_CHANGE_VIA_WEB,
                                                "action": InviteModelAction.UPDATE, "changes": changes})
                messages.success(request, "Invite to %s was successfully updated." % data["email"])
            elif domain_request is not None:
                domain_request.is_approved = True
                domain_request.save()
                if user is not None:
                    domain_request.send_approval_email()
                    create_invitation = False
                    user.add_as_web_user(self.domain, role=data["role"],
                                         primary_location_id=data.get("primary_location", None),
                                         program_id=data.get("program", None),
                                         assigned_location_ids=data.get("assigned_locations", None),
                                         profile=profile,
                                         custom_user_data=data.get("custom_user_data"),
                                         tableau_role=data.get("tableau_role", None),
                                         tableau_group_ids=data.get("tableau_group_ids", None)
                                         )
                messages.success(request, "%s added." % data["email"])
            else:
                track_workflow_noop(request.couch_user.get_email(),
                                    "Sent a project invitation",
                                    {"Sent a project invitation": "yes"})
                send_hubspot_form(HUBSPOT_INVITATION_SENT_FORM, request)
                messages.success(request, "Invitation sent to %s" % data["email"])

            if create_invitation:
                data["invited_by"] = request.couch_user.user_id
                data["invited_on"] = datetime.utcnow()
                data["domain"] = self.domain
                data["profile"] = profile
                data["primary_location"], assigned_locations = self._get_sql_locations(
                    data.pop("primary_location", None), data.pop("assigned_locations", []))
                invite = Invitation(**data)
                changes = self.format_changes(self.domain,
                                              {'role_name': data.get("role"),
                                               'profile': profile,
                                               'assigned_locations': assigned_locations,
                                               'primary_location': data["primary_location"],
                                               'program_id': data.get("program", None)})
                for key in changes:
                    if key in data:
                        data.pop(key, None)
                data.pop("primary_location", None)
                changes.update(data)
                invite.save(logging_values={"changed_by": request.couch_user.user_id,
                                            "changed_via": INVITATION_CHANGE_VIA_WEB,
                                            "action": InviteModelAction.CREATE, "changes": changes})
                invite.assigned_locations.set(assigned_locations)
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

    def _get_sql_locations(self, primary_location_id, assigned_location_ids):
        primary_location = (SQLLocation.by_location_id(primary_location_id) if primary_location_id else None)
        if primary_location_id:
            assert primary_location_id in assigned_location_ids
        self._assert_user_has_permission_to_access_locations(assigned_location_ids)
        assigned_locations = [SQLLocation.by_location_id(assigned_location_id)
                              for assigned_location_id in assigned_location_ids
                              if assigned_location_id is not None]
        return primary_location, assigned_locations

    def _get_and_set_changes(self, invite, form_data, profile):
        change_values = {}
        role = form_data.get("role")
        if invite.role != role:
            change_values['role_name'] = role
            invite.role = role
        if invite.profile != profile:
            change_values['profile'] = profile
            invite.profile = profile
        primary_location, assigned_locations = self._get_sql_locations(
            form_data.pop("primary_location", None), form_data.pop("assigned_locations", []))
        previous_locations = [loc for loc in invite.assigned_locations.all()]
        if len(assigned_locations) != len(previous_locations) \
           or set(assigned_locations) != set(previous_locations):
            change_values['assigned_locations'] = assigned_locations
            invite.assigned_locations.set(assigned_locations)
        if invite.primary_location != primary_location:
            change_values['primary_location'] = primary_location
            invite.primary_location = primary_location
        if invite.program != form_data.get("program", None):
            program = form_data.get("program", None)
            change_values['program_id'] = program
            invite.program = program
        if invite.tableau_role != form_data.get("tableau_role", None):
            tableau_role = form_data.get("program", None)
            change_values['tableau_role'] = tableau_role
            invite.tableau_role = tableau_role
        if invite.tableau_group_ids != form_data.get("tableau_group_ids", None):
            tableau_group_ids = form_data.get("tableau_group_ids", None)
            change_values['tableau_group_ids'] = tableau_group_ids
            invite.program = tableau_group_ids

        return invite, change_values

    @staticmethod
    def format_changes(domain, changed_values):
        role_name = changed_values.pop("role_name", None)
        if role_name:
            if role_name == "admin":
                role = StaticRole.domain_admin(domain)
            else:
                try:
                    role = UserRole.objects.get(couch_id=role_name.replace("user-role:", ''), domain=domain)
                except UserRole.DoesNotExist:
                    role = None
            if role:
                changed_values.update(UserChangeMessage.role_change(role))
        profile = changed_values.pop('profile', None)
        if profile:
            changed_values.update(UserChangeMessage.profile_info(profile.id, profile.name))
        program_id = changed_values.pop('program_id', None)
        if program_id:
            changed_values.update(UserChangeMessage.program_change(Program.get(program_id)))
        assigned_locations = changed_values.pop('assigned_locations', None)
        if assigned_locations:
            changed_values.update(UserChangeMessage.assigned_locations_info(assigned_locations))
        primary_location = changed_values.pop('primary_location', None)
        if primary_location:
            changed_values.update(UserChangeMessage.primary_location_info(primary_location))

        return changed_values


class BaseUploadUser(BaseUserSettingsView):
    def post(self, request, *args, **kwargs):
        """View's dispatch method automatically calls this"""
        try:
            workbook = get_workbook(request.FILES.get("bulk_upload_file"))
            user_specs, group_specs = self.process_workbook(
                workbook,
                self.domain,
                self.is_web_upload,
                request.couch_user
            )
            task_ref = self.upload_users(
                request, user_specs, group_specs, self.domain, self.is_web_upload)
            return self._get_success_response(request, task_ref)
        except WorkbookJSONError as e:
            messages.error(request, str(e))
            return self.get(request, *args, **kwargs)
        except WorksheetNotFound:
            return HttpResponseBadRequest("Workbook has no worksheets")
        except UserUploadError as e:
            messages.error(request, _(str(e)))
            return HttpResponseRedirect(reverse(self.urlname, args=[self.domain]))

    @staticmethod
    def process_workbook(workbook, domain, is_web_upload, upload_user):
        from corehq.apps.user_importer.importer import check_headers

        try:
            user_specs = workbook.get_worksheet(title="users")
        except WorksheetNotFound:
            try:
                user_specs = workbook.get_worksheet()
            except WorksheetNotFound as e:
                raise WorksheetNotFound("Workbook has no worksheets") from e

        check_headers(user_specs, domain, upload_couch_user=upload_user, is_web_upload=is_web_upload)

        try:
            group_specs = workbook.get_worksheet(title="groups")
        except WorksheetNotFound:
            group_specs = []

        return user_specs, group_specs

    @staticmethod
    def upload_users(request, user_specs, group_specs, domain, is_web_upload):
        task_ref = expose_cached_download(payload=None, expiry=1 * 60 * 60, file_extension=None)

        if PARALLEL_USER_IMPORTS.enabled(domain) and not is_web_upload:
            if list(group_specs):
                raise UserUploadError(
                    "Groups are not allowed with parallel user import. Please upload them separately")

            task = parallel_user_import.delay(
                domain,
                list(user_specs),
                request.couch_user.user_id
            )
        else:
            upload_record = UserUploadRecord(
                domain=domain,
                user_id=request.couch_user.user_id
            )
            upload_record.save()

            task = import_users_and_groups.delay(
                domain,
                list(user_specs),
                list(group_specs),
                request.couch_user.user_id,
                upload_record.pk,
                is_web_upload
            )

        task_ref.set_task(task)
        return task_ref

    def _get_success_response(self, request, task_ref):
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


@location_safe
class UploadWebUsers(BaseUploadUser):
    template_name = 'hqwebapp/bootstrap3/bulk_upload.html'
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
        track_workflow_noop(request.couch_user.get_email(), 'Bulk upload web users selected')
        return super(UploadWebUsers, self).post(request, *args, **kwargs)


@location_safe
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


@location_safe
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
    if (not commcare_user or not user_can_access_other_user(domain, request.couch_user, commcare_user)
            or (toggles.TWO_STAGE_USER_PROVISIONING.enabled(domain) and commcare_user.self_set_password)):
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
    return JsonResponse(json_dump)


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
