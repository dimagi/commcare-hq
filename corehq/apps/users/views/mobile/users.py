import io
import json
import re
import time

from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import ValidationError
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.http.response import HttpResponseServerError, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop, override
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView, View

from braces.views import JsonRequestResponseMixin
from couchdbkit import ResourceNotFound
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege
from memoized import memoized

from casexml.apps.phone.models import SyncLogSQL
from couchexport.models import Format
from couchexport.writers import Excel2007ExportWriter
from soil import DownloadBase
from soil.exceptions import TaskFailedError
from soil.util import get_download_context

from corehq import privileges, toggles
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    EntryPoint,
    Subscription,
)
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.analytics.tasks import track_workflow
from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.models import (
    CUSTOM_DATA_FIELD_PREFIX,
    PROFILE_SLUG,
)
from corehq.apps.domain.auth import get_connectid_userinfo
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    login_or_basic_ex,
)
from corehq.apps.domain.extension_points import has_custom_clean_password
from corehq.apps.domain.models import SMSAccountConfirmationSettings
from corehq.apps.domain.utils import guess_domain_language_for_sms
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.es import FormES
from corehq.apps.events.models import (
    get_attendee_case_type,
    mobile_worker_attendees_enabled,
)
from corehq.apps.events.tasks import create_attendee_for_user
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.crispy import make_form_readonly
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import (
    location_safe,
    user_can_access_location_id,
)
from corehq.apps.ota.utils import demo_restore_date_created, turn_off_demo_mode
from corehq.apps.registration.forms import (
    MobileWorkerAccountConfirmationBySMSForm,
    MobileWorkerAccountConfirmationForm,
)
from corehq.apps.sms.api import send_sms
from corehq.apps.sms.verify import initiate_sms_verification_workflow
from corehq.apps.users.account_confirmation import (
    send_account_confirmation_if_necessary,
    send_account_confirmation_sms_if_necessary,
)
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.bulk_download import (
    get_domains_from_user_filters,
    load_memoizer,
)
from corehq.apps.users.dbaccessors import get_user_docs_by_username
from corehq.apps.users.decorators import (
    require_can_edit_commcare_users,
    require_can_edit_or_view_commcare_users,
    require_can_edit_web_users,
    require_can_use_filtered_user_download,
)
from corehq.apps.users.exceptions import InvalidRequestException
from corehq.apps.users.forms import (
    CommCareAccountForm,
    CommCareUserFormSet,
    CommtrackUserForm,
    ConfirmExtraUserChargesForm,
    MultipleSelectionForm,
    NewMobileWorkerForm,
    SetUserPasswordForm,
    UserFilterForm,
)
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    DeactivateMobileWorkerTrigger,
    check_and_send_limit_email,
    ConnectIDUserLink
)
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.tasks import (
    bulk_download_usernames_async,
    bulk_download_users_async,
    reset_demo_user_restore_task,
    turn_on_demo_mode_task,
)
from corehq.apps.users.util import (
    can_add_extra_mobile_workers,
    format_username,
    generate_mobile_username,
    log_user_change,
    raw_username,
)
from corehq.apps.users.views import (
    BaseEditUserView,
    BaseManageWebUserView,
    BaseUploadUser,
    BaseUserSettingsView,
    UserUploadJobPollView,
    get_domain_languages,
)
from corehq.apps.users.views.utils import get_user_location_info
from corehq.const import (
    USER_CHANGE_VIA_BULK_IMPORTER,
    USER_CHANGE_VIA_WEB,
    USER_DATE_FORMAT,
)
from corehq.motech.utils import b64_aes_decrypt
from corehq.pillows.utils import MOBILE_USER_TYPE, WEB_USER_TYPE
from corehq.util import get_document_or_404
from corehq.util.dates import iso_string_to_datetime
from corehq.util.jqueryrmi import JSONResponseMixin, allow_remote_invocation
from corehq.util.metrics import metrics_counter
from corehq.util.workbook_json.excel import (
    WorkbookJSONError,
    WorksheetNotFound,
    get_workbook,
)

from ..utils import log_user_groups_change
from .custom_data_fields import UserFieldsView

BULK_MOBILE_HELP_SITE = ("https://confluence.dimagi.com/display/commcarepublic"
                         "/Create+and+Manage+CommCare+Mobile+Workers#Createand"
                         "ManageCommCareMobileWorkers-B.UseBulkUploadtocreatem"
                         "ultipleusersatonce")
DEFAULT_USER_LIST_LIMIT = 10
BAD_MOBILE_USERNAME_REGEX = re.compile("[^A-Za-z0-9.+-_]")


def _can_edit_workers_location(web_user, mobile_worker):
    if web_user.has_permission(mobile_worker.domain, 'access_all_locations'):
        return True
    loc_id = mobile_worker.location_id
    if not loc_id:
        return False
    return user_can_access_location_id(mobile_worker.domain, web_user, loc_id)


@location_safe
class EditCommCareUserView(BaseEditUserView):
    urlname = "edit_commcare_user"
    page_title = gettext_noop("Edit Mobile Worker")

    @property
    def page_name(self):
        if self.request.is_view_only:
            return _("Edit Mobile Worker (View Only)")
        return self.page_title

    @property
    def template_name(self):
        if self.editable_user.is_deleted():
            return "users/deleted_account.html"
        else:
            return "users/edit_commcare_user.html"

    @use_multiselect
    @method_decorator(require_can_edit_or_view_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(EditCommCareUserView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(EditCommCareUserView, self).main_context
        profiles = [profile.to_json() for profile in self.form_user_update.custom_data.model.get_profiles()]
        context.update({
            'custom_fields_slugs': [f.slug for f in self.form_user_update.custom_data.fields],
            'custom_fields_profiles': sorted(profiles, key=lambda x: x['name'].lower()),
            'custom_fields_profile_slug': PROFILE_SLUG,
            'user_data': self.editable_user.get_user_data(self.domain).to_dict(),
            'edit_user_form_title': self.edit_user_form_title,
            'strong_mobile_passwords': self.request.project.strong_mobile_passwords,
            'has_any_sync_logs': self.has_any_sync_logs,
        })
        return context

    @property
    def has_any_sync_logs(self):
        return SyncLogSQL.objects.filter(user_id=self.editable_user_id).exists()

    @property
    @memoized
    def editable_user(self):
        try:
            user = CouchUser.get_by_user_id(self.editable_user_id, self.domain)
        except (ResourceNotFound, CouchUser.AccountTypeError, KeyError):
            raise Http404()
        if not user or not _can_edit_workers_location(self.couch_user, user):
            raise Http404()
        return user

    @property
    def edit_user_form_title(self):
        return _("Information for %s") % self.editable_user.human_friendly_name

    @property
    def is_currently_logged_in_user(self):
        return self.editable_user_id == self.couch_user._id

    @property
    @memoized
    def reset_password_form(self):
        return SetUserPasswordForm(self.request.project, self.editable_user_id, user="")

    @property
    @memoized
    def groups(self):
        if not self.editable_user:
            return []
        return Group.by_user_id(self.editable_user_id)

    @property
    @memoized
    def all_groups(self):
        # note: will slow things down if there are loads of groups. worth it?
        # justification: ~every report already does this.
        return Group.by_domain(self.domain)

    @property
    @memoized
    def group_form(self):
        form = MultipleSelectionForm(initial={
            'selected_ids': [g._id for g in self.groups],
        })
        form.fields['selected_ids'].choices = [(g._id, g.name) for g in self.all_groups]
        return form

    @property
    @memoized
    def commtrack_form(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "commtrack":
            return CommtrackUserForm(self.request.POST, request=self.request, domain=self.domain)

        # currently only support one location on the UI
        linked_loc = self.editable_user.location
        initial_id = linked_loc._id if linked_loc else None
        program_id = self.editable_user.get_domain_membership(self.domain).program_id
        assigned_locations = self.editable_user.assigned_location_ids
        return CommtrackUserForm(
            domain=self.domain,
            request=self.request,
            initial={
                'primary_location': initial_id,
                'program_id': program_id,
                'assigned_locations': assigned_locations}
        )

    @property
    def page_context(self):

        if self.request.is_view_only:
            make_form_readonly(self.commtrack_form)
            make_form_readonly(self.form_user_update.user_form)
            make_form_readonly(self.form_user_update.custom_data.form)

        warning_banner_info = None
        if self.domain_object.orphan_case_alerts_warning:
            warning_banner_info = get_user_location_info(
                domain=self.domain,
                user_location_ids=self.editable_user.assigned_location_ids,
                user_id=self.editable_user.user_id
            )

        can_edit_groups = self.request.couch_user.has_permission(self.domain, 'edit_groups')
        can_access_all_locations = self.request.couch_user.has_permission(self.domain, 'access_all_locations')
        locations_present = users_have_locations(self.domain)
        request_has_locations_privilege = has_privilege(self.request, privileges.LOCATIONS)
        context = {
            'are_groups': bool(len(self.all_groups)),
            'groups_url': reverse('all_groups', args=[self.domain]),
            'group_form': self.group_form,
            'reset_password_form': self.reset_password_form,
            'is_currently_logged_in_user': self.is_currently_logged_in_user,
            'data_fields_form': self.form_user_update.custom_data.form,
            'can_use_inbound_sms': domain_has_privilege(self.domain, privileges.INBOUND_SMS),
            'show_deactivate_after_date': self.form_user_update.user_form.show_deactivate_after_date,
            'can_create_groups': can_edit_groups and can_access_all_locations,
            'needs_to_downgrade_locations': locations_present and not request_has_locations_privilege,
            'demo_restore_date': naturaltime(demo_restore_date_created(self.editable_user)),
            'group_names': [g.name for g in self.groups],
            'warning_banner_info': warning_banner_info
        }
        if self.commtrack_form.errors:
            messages.error(self.request, _(
                "There were some errors while saving user's locations. Please check the 'Locations' tab"
            ))
        if self.domain_object.commtrack_enabled or self.domain_object.uses_locations:
            context.update({
                'commtrack_enabled': self.domain_object.commtrack_enabled,
                'uses_locations': self.domain_object.uses_locations,
                'commtrack': {
                    'update_form': self.commtrack_form,
                },
            })
        return context

    @property
    def user_role_choices(self):
        role_choices = self.editable_role_choices
        default_role = UserRole.commcare_user_default(self.domain)
        return [(default_role.get_qualified_id(), default_role.name)] + role_choices

    @property
    @memoized
    def form_user_update(self):
        if (self.request.method == "POST"
                and self.request.POST['form_type'] == "update-user"
                and not self.request.is_view_only):
            data = self.request.POST
        else:
            data = None
        form = CommCareUserFormSet(data=data, domain=self.domain,
            editable_user=self.editable_user, request_user=self.request.couch_user, request=self.request)

        form.user_form.load_language(language_choices=get_domain_languages(self.domain))

        if self.can_change_user_roles or self.couch_user.can_view_roles():
            form.user_form.load_roles(current_role=self.existing_role, role_choices=self.user_role_choices)
        else:
            del form.user_form.fields['role']

        return form

    @property
    def parent_pages(self):
        return [{
            'title': MobileWorkerListView.page_title,
            'url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
        }]

    def post(self, request, *args, **kwargs):
        if self.request.is_view_only:
            messages.error(
                request,
                _("You do not have permission to update Mobile Workers.")
            )
            return super(EditCommCareUserView, self).get(request, *args, **kwargs)
        if self.request.POST['form_type'] == "add-phonenumber":
            phone_number = self.request.POST['phone_number']
            phone_number = re.sub(r'\s', '', phone_number)
            if re.match(r'\d+$', phone_number):
                is_new_phone_number = phone_number not in self.editable_user.phone_numbers
                self.editable_user.add_phone_number(phone_number)
                self.editable_user.save(spawn_task=True)
                if is_new_phone_number:
                    log_user_change(
                        by_domain=self.request.domain,
                        for_domain=self.editable_user.domain,
                        couch_user=self.editable_user,
                        changed_by_user=self.request.couch_user,
                        changed_via=USER_CHANGE_VIA_WEB,
                        change_messages=UserChangeMessage.phone_numbers_added([phone_number])
                    )
                messages.success(request, _("Phone number added."))
            else:
                messages.error(request, _("Please enter digits only."))
        return super(EditCommCareUserView, self).post(request, *args, **kwargs)


class ConfirmBillingAccountForExtraUsersView(BaseUserSettingsView, AsyncHandlerMixin):
    urlname = 'extra_users_confirm_billing'
    template_name = 'users/extra_users_confirm_billing.html'
    page_title = gettext_noop("Confirm Billing Information")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    @memoized
    def account(self):
        account = BillingAccount.get_or_create_account_by_domain(
            self.domain,
            created_by=self.couch_user.username,
            account_type=BillingAccountType.USER_CREATED,
            entry_point=EntryPoint.SELF_STARTED,
        )[0]
        return account

    @property
    @memoized
    def billing_info_form(self):
        if self.request.method == 'POST':
            return ConfirmExtraUserChargesForm(
                self.account, self.domain, self.request.couch_user.username, data=self.request.POST
            )
        return ConfirmExtraUserChargesForm(self.account, self.domain, self.request.couch_user.username)

    @property
    def page_context(self):
        return {
            'billing_info_form': self.billing_info_form,
        }

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if self.account.date_confirmed_extra_charges is not None:
            return HttpResponseRedirect(reverse(MobileWorkerListView.urlname, args=[self.domain]))
        return super(ConfirmBillingAccountForExtraUsersView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.billing_info_form.is_valid():
            is_saved = self.billing_info_form.save()
            if not is_saved:
                messages.error(
                    request, _("It appears that there was an issue updating your contact information. "
                               "We've been notified of the issue. Please try submitting again, and if the problem "
                               "persists, please try in a few hours."))
            else:
                messages.success(
                    request, _("Billing contact information was successfully confirmed. "
                               "You may now add additional Mobile Workers.")
                )
                return HttpResponseRedirect(reverse(
                    MobileWorkerListView.urlname, args=[self.domain]
                ))
        return self.get(request, *args, **kwargs)


@require_can_edit_commcare_users
@location_safe
@require_POST
def delete_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    if not _can_edit_workers_location(request.couch_user, user):
        raise PermissionDenied()

    user_location_id = user.user_location_id
    if (user_location_id and SQLLocation.objects.get_or_None(location_id=user_location_id, user_id=user._id)):
        messages.error(request, _("This is a location user. You must delete the "
                       "corresponding location before you can delete this user."))
        return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]))
    user.retire(request.domain, deleted_by=request.couch_user, deleted_via=USER_CHANGE_VIA_WEB)
    messages.success(request, _("""User %s has been deleted. All their submissions and cases will be permanently
        deleted in the next few minutes""") % user.username)
    return HttpResponseRedirect(reverse(MobileWorkerListView.urlname, args=[domain]))


@require_can_edit_commcare_users
@location_safe
@require_POST
def force_user_412(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    if not _can_edit_workers_location(request.couch_user, user):
        raise PermissionDenied()

    metrics_counter('commcare.force_user_412.count', tags={'domain': domain})

    SyncLogSQL.objects.filter(user_id=user_id).delete()

    messages.success(
        request,
        "Mobile Worker {}'s device data will be hard refreshed the next time they sync."
        .format(user.human_friendly_name)
    )
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]) + '#user-permanent')


@require_can_edit_commcare_users
@require_POST
def restore_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    success, message = user.unretire(request.domain, unretired_by=request.couch_user,
                                     unretired_via=USER_CHANGE_VIA_WEB)
    if success:
        messages.success(request, "User %s and all their submissions have been restored" % user.username)
    else:
        messages.error(request, message)
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]))


@require_can_edit_commcare_users
@require_POST
def toggle_demo_mode(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    demo_mode = request.POST.get('demo_mode', 'no')
    demo_mode = True if demo_mode == 'yes' else False

    edit_user_url = reverse(EditCommCareUserView.urlname, args=[domain, user_id])
    # handle bad POST param
    if user.is_demo_user == demo_mode:
        warning = _("User is already in Demo mode!") if user.is_demo_user else _("User is not in Demo mode!")
        messages.warning(request, warning)
        return HttpResponseRedirect(edit_user_url)

    if demo_mode:
        download = DownloadBase()
        res = turn_on_demo_mode_task.delay(user.get_id, domain)
        download.set_task(res)
        return HttpResponseRedirect(
            reverse(
                DemoRestoreStatusView.urlname,
                args=[domain, download.download_id, user_id]
            )
        )
    else:
        from corehq.apps.app_manager.views.utils import (
            get_practice_mode_configured_apps,
            unset_practice_mode_configured_apps,
        )

        # if the user is being used as practice user on any apps, check/ask for confirmation
        apps = get_practice_mode_configured_apps(domain)
        confirm_turn_off = True if (request.POST.get('confirm_turn_off', 'no')) == 'yes' else False
        if apps and not confirm_turn_off:
            return HttpResponseRedirect(reverse(ConfirmTurnOffDemoModeView.urlname, args=[domain, user_id]))

        turn_off_demo_mode(user)
        unset_practice_mode_configured_apps(domain, user.get_id)
        messages.success(request, _("Successfully turned off demo mode!"))
    return HttpResponseRedirect(edit_user_url)


class BaseManageCommCareUserView(BaseUserSettingsView):

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseManageCommCareUserView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': MobileWorkerListView.page_title,
            'url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
        }]


class ConfirmTurnOffDemoModeView(BaseManageCommCareUserView):
    template_name = 'users/confirm_turn_off_demo_mode.html'
    urlname = 'confirm_turn_off_demo_mode'
    page_title = gettext_noop("Turn off Demo mode")

    @property
    def page_context(self):
        from corehq.apps.app_manager.views.utils import (
            get_practice_mode_configured_apps,
        )
        user_id = self.kwargs.pop('couch_user_id')
        user = CommCareUser.get_by_user_id(user_id, self.domain)
        practice_apps = get_practice_mode_configured_apps(self.domain, user_id)
        return {
            'commcare_user': user,
            'practice_apps': practice_apps,
        }

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class DemoRestoreStatusView(BaseManageCommCareUserView):
    urlname = 'demo_restore_status'
    page_title = gettext_noop('Demo User Status')

    def dispatch(self, request, *args, **kwargs):
        return super(DemoRestoreStatusView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context = super(DemoRestoreStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('demo_restore_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Demo User status"),
            'progress_text': _("Getting latest restore data, please wait"),
            'error_text': _("There was an unexpected error! Please try again or report an issue."),
            'next_url': reverse(EditCommCareUserView.urlname, args=[self.domain, kwargs['user_id']]),
            'next_url_text': _("Go back to Edit Mobile Worker"),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_commcare_users
def demo_restore_job_poll(request, domain, download_id, template="users/mobile/partials/demo_restore_status.html"):

    try:
        context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': _('Done'),
        'on_complete_long': _('User is now in Demo mode with latest restore!'),

    })
    return render(request, template, context)


@require_can_edit_commcare_users
@require_POST
def reset_demo_user_restore(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    if not user.is_demo_user:
        warning = _("The user is not a demo user.")
        messages.warning(request, warning)
        return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]))

    download = DownloadBase()
    res = reset_demo_user_restore_task.delay(user.get_id, domain)
    download.set_task(res)

    return HttpResponseRedirect(
        reverse(
            DemoRestoreStatusView.urlname,
            args=[domain, download.download_id, user_id]
        )
    )


@require_can_edit_commcare_users
@require_POST
def update_user_groups(request, domain, couch_user_id):
    form = MultipleSelectionForm(request.POST)
    form.fields['selected_ids'].choices = [(id, 'throwaway') for id in Group.ids_by_domain(domain)]
    if form.is_valid():
        user = CommCareUser.get(couch_user_id)
        old_group_ids = user.get_group_ids()
        new_group_ids = form.cleaned_data['selected_ids']
        assert user.doc_type == "CommCareUser"
        assert user.domain == domain
        user.set_groups(new_group_ids)
        if old_group_ids != new_group_ids:
            log_user_groups_change(domain, request, user, new_group_ids)
        messages.success(request, _("User groups updated!"))
    else:
        messages.error(request, _("Form not valid. A group may have been deleted while you were viewing this page"
                                  "Please try again."))
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id]))


@location_safe
class MobileWorkerListView(JSONResponseMixin, BaseUserSettingsView):
    template_name = 'users/mobile_workers.html'
    urlname = 'mobile_workers'
    page_title = gettext_noop("Mobile Workers")

    @method_decorator(require_can_edit_or_view_commcare_users)
    def dispatch(self, *args, **kwargs):
        return super(MobileWorkerListView, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def can_access_all_locations(self):
        return self.couch_user.has_permission(self.domain, 'access_all_locations')

    @property
    def can_bulk_edit_users(self):
        return has_privilege(self.request, privileges.BULK_USER_MANAGEMENT) and not self.request.is_view_only

    @property
    def can_add_extra_users(self):
        return can_add_extra_mobile_workers(self.request)

    @property
    @memoized
    def new_mobile_worker_form(self):
        if self.request.method == "POST":
            return NewMobileWorkerForm(self.request.project, self.couch_user, self.request.POST)
        return NewMobileWorkerForm(self.request.project, self.couch_user)

    @property
    @memoized
    def custom_data(self):
        return CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            post_dict=self.request.POST if self.request.method == "POST" else None,
            required_only=True,
            ko_model="custom_fields",
        )

    @property
    def two_stage_user_confirmation(self):
        return toggles.TWO_STAGE_USER_PROVISIONING.enabled(
            self.domain
        ) or toggles.TWO_STAGE_USER_PROVISIONING_BY_SMS.enabled(self.domain)

    @property
    def page_context(self):
        bulk_download_url = reverse(FilteredCommCareUserDownload.urlname, args=[self.domain])

        profiles = [profile.to_json() for profile in self.custom_data.model.get_profiles()]
        return {
            'new_mobile_worker_form': self.new_mobile_worker_form,
            'custom_fields_form': self.custom_data.form,
            'custom_fields_slugs': [f.slug for f in self.custom_data.fields],
            'custom_fields_profiles': profiles,
            'custom_fields_profile_slug': PROFILE_SLUG,
            'can_bulk_edit_users': self.can_bulk_edit_users,
            'can_add_extra_users': self.can_add_extra_users,
            'can_access_all_locations': self.can_access_all_locations,
            'skip_standard_password_validations': has_custom_clean_password(),
            'pagination_limit_cookie_name': (
                'hq.pagination.limit.mobile_workers_list.%s' % self.domain),
            'can_edit_billing_info': self.request.couch_user.is_domain_admin(self.domain),
            'strong_mobile_passwords': self.request.project.strong_mobile_passwords,
            'bulk_download_url': bulk_download_url,
            'show_deactivate_after_date': self.new_mobile_worker_form.show_deactivate_after_date,
            'two_stage_user_confirmation': self.two_stage_user_confirmation,
        }

    @property
    @memoized
    def query(self):
        return self.request.GET.get('query')

    @allow_remote_invocation
    def check_username(self, in_data):
        try:
            username = generate_mobile_username(in_data['username'].strip(), self.domain)
        except ValidationError as e:
            return {'error': e.message}
        else:
            return {'success': _('Username {} is available').format(username)}

    @allow_remote_invocation
    def create_mobile_worker(self, in_data):
        if self.request.is_view_only:
            return {
                'error': _("You do not have permission to create mobile workers.")
            }

        try:
            self._ensure_proper_request(in_data)
            form_data = self._construct_form_data(in_data)
        except InvalidRequestException as e:
            return {
                'error': str(e)
            }

        self.request.POST = form_data

        if not (self.new_mobile_worker_form.is_valid() and self.custom_data.is_valid()):
            all_errors = [e for errors in self.new_mobile_worker_form.errors.values() for e in errors]
            all_errors += [e for errors in self.custom_data.errors.values() for e in errors]
            return {'error': _("Forms did not validate: {errors}").format(
                errors=', '.join(all_errors)
            )}
        couch_user = self._build_commcare_user()
        if (
            domain_has_privilege(self.domain, privileges.ATTENDANCE_TRACKING)
            and toggles.ATTENDANCE_TRACKING.enabled(self.domain)
            and mobile_worker_attendees_enabled(self.domain)
        ):
            self.create_attendee_for_user(couch_user)

        if self.new_mobile_worker_form.cleaned_data['send_account_confirmation_email']:
            send_account_confirmation_if_necessary(couch_user)
        if self.new_mobile_worker_form.cleaned_data['force_account_confirmation_by_sms']:
            phone_number = self.new_mobile_worker_form.cleaned_data['phone_number']
            couch_user.set_default_phone_number(phone_number)
            send_account_confirmation_sms_if_necessary(couch_user)

        plan_limit, user_count = Subscription.get_plan_and_user_count_by_domain(self.domain)
        check_and_send_limit_email(self.domain, plan_limit, user_count, user_count - 1)
        return {
            'success': True,
            'user_id': couch_user.userID,
        }

    def create_attendee_for_user(self, commcare_user):
        """Creates a case for commcare_user to be used for attendance tracking"""
        create_attendee_for_user(
            commcare_user,
            case_type=get_attendee_case_type(self.domain),
            domain=self.domain,
            xform_user_id=self.couch_user.user_id,
            xform_device_id='MobileWorkerListView.'
                            'create_attendee_for_commcare_user',
        )

    def _build_commcare_user(self):
        username = self.new_mobile_worker_form.cleaned_data['username']
        password = self.new_mobile_worker_form.cleaned_data['new_password']
        first_name = self.new_mobile_worker_form.cleaned_data['first_name']
        email = self.new_mobile_worker_form.cleaned_data['email']
        last_name = self.new_mobile_worker_form.cleaned_data['last_name']
        location_id = self.new_mobile_worker_form.cleaned_data['location_id']
        is_account_confirmed = not (
            self.new_mobile_worker_form.cleaned_data['force_account_confirmation']
            or self.new_mobile_worker_form.cleaned_data['force_account_confirmation_by_sms'])

        role_id = UserRole.commcare_user_default(self.domain).get_id
        commcare_user = CommCareUser.create(
            self.domain,
            username,
            password,
            created_by=self.request.couch_user,
            created_via=USER_CHANGE_VIA_WEB,
            email=email,
            device_id="Generated from HQ",
            first_name=first_name,
            last_name=last_name,
            user_data=self.custom_data.get_data_to_save(),
            is_account_confirmed=is_account_confirmed,
            location=SQLLocation.objects.get(domain=self.domain, location_id=location_id) if location_id else None,
            role_id=role_id
        )

        if self.new_mobile_worker_form.show_deactivate_after_date:
            DeactivateMobileWorkerTrigger.update_trigger(
                self.domain,
                commcare_user.user_id,
                self.new_mobile_worker_form.cleaned_data['deactivate_after_date']
            )

        return commcare_user

    def _ensure_proper_request(self, in_data):
        if not self.can_add_extra_users:
            raise InvalidRequestException(_("No Permission."))

        if 'user' not in in_data:
            raise InvalidRequestException(_("Please provide mobile worker data."))

        return None

    def _construct_form_data(self, in_data):
        try:
            user_data = in_data['user']
            form_data = {
                'username': user_data.get('username'),
                'new_password': user_data.get('password'),
                'first_name': user_data.get('first_name'),
                'last_name': user_data.get('last_name'),
                'location_id': user_data.get('location_id'),
                'email': user_data.get('email'),
                'force_account_confirmation': user_data.get('force_account_confirmation'),
                'send_account_confirmation_email': user_data.get('send_account_confirmation_email'),
                'force_account_confirmation_by_sms': user_data.get('force_account_confirmation_by_sms'),
                'phone_number': user_data.get('phone_number'),
                'deactivate_after_date': user_data.get('deactivate_after_date'),
                'domain': self.domain,
            }
            for k, v in user_data.get('custom_fields', {}).items():
                form_data["{}-{}".format(CUSTOM_DATA_FIELD_PREFIX, k)] = v
            return form_data
        except Exception as e:
            raise InvalidRequestException(_("Check your request: {}").format(e))


@require_can_edit_commcare_users
@require_POST
@location_safe
def activate_commcare_user(request, domain, user_id):
    return _modify_user_status(request, domain, user_id, True)


@require_can_edit_commcare_users
@require_POST
@location_safe
def deactivate_commcare_user(request, domain, user_id):
    return _modify_user_status(request, domain, user_id, False)


def _modify_user_status(request, domain, user_id, is_active):
    user = CommCareUser.get_by_user_id(user_id, domain)
    if (not _can_edit_workers_location(request.couch_user, user)
            or (is_active and not can_add_extra_mobile_workers(request))):
        return JsonResponse({
            'error': _("No Permission."),
        })
    if not is_active and user.user_location_id:
        return JsonResponse({
            'error': _("This is a location user, archive or delete the "
                       "corresponding location to deactivate it."),
        })
    user.is_active = is_active
    user.save(spawn_task=True)
    log_user_change(by_domain=request.domain, for_domain=user.domain,
                    couch_user=user, changed_by_user=request.couch_user,
                    changed_via=USER_CHANGE_VIA_WEB, fields_changed={'is_active': user.is_active})
    return JsonResponse({
        'success': True,
    })


@require_can_edit_commcare_users
@require_POST
@location_safe
def send_confirmation_email(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    send_account_confirmation_if_necessary(user)
    return JsonResponse(data={'success': True})


@require_POST
@location_safe
def send_confirmation_sms(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    send_account_confirmation_sms_if_necessary(user)
    return JsonResponse(data={'success': True})


@require_can_edit_or_view_commcare_users
@require_GET
@location_safe
def paginate_mobile_workers(request, domain):
    limit = int(request.GET.get('limit', 10))
    page = int(request.GET.get('page', 1))
    query = request.GET.get('query')
    deactivated_only = json.loads(request.GET.get('showDeactivatedUsers', "false"))

    def _user_query(search_string, page, limit):
        user_es = get_search_users_in_domain_es_query(
            domain=domain, search_string=search_string,
            offset=page * limit, limit=limit)
        if not request.couch_user.has_permission(domain, 'access_all_locations'):
            loc_ids = (SQLLocation.objects.accessible_to_user(domain, request.couch_user)
                                          .location_ids())
            user_es = user_es.location(list(loc_ids))
        return user_es.mobile_users()

    # backend pages start at 0
    users_query = _user_query(query, page - 1, limit)
    # run with a blank query to fetch total records with same scope as in search
    if deactivated_only:
        users_query = users_query.show_only_inactive()
    users_data = users_query.source([
        '_id',
        'first_name',
        'last_name',
        'base_username',
        'created_on',
        'is_active',
        'is_account_confirmed',
    ]).run()
    users = users_data.hits

    def _status_string(user_data):
        if user_data['is_active']:
            return _('Active')
        elif user_data['is_account_confirmed']:
            return _('Deactivated')
        else:
            return _('Pending Confirmation')

    for user in users:
        date_registered = user.pop('created_on', '')
        if date_registered:
            date_registered = iso_string_to_datetime(date_registered).strftime(USER_DATE_FORMAT)
        # make sure these are always set and default to true
        user['is_active'] = user.get('is_active', True)
        user['is_account_confirmed'] = user.get('is_account_confirmed', True)
        user.update({
            'username': user.pop('base_username', ''),
            'user_id': user.pop('_id'),
            'date_registered': date_registered,
            'status': _status_string(user),
        })

    return JsonResponse({
        'users': users,
        'total': users_data.total,
    })


class CreateCommCareUserModal(JsonRequestResponseMixin, DomainViewMixin, View):
    template_name = "users/new_mobile_worker_modal.html"
    urlname = 'new_mobile_worker_modal'

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        if not can_add_extra_mobile_workers(request):
            raise PermissionDenied()
        return super(CreateCommCareUserModal, self).dispatch(request, *args, **kwargs)

    def render_form(self, status):
        if domain_has_privilege(self.domain, privileges.APP_USER_PROFILES):
            return self.render_json_response({
                "status": "failure",
                "form_html": "<div class='alert alert-danger'>{}</div>".format(_("""
                    Cannot add new worker due to usage of user field profiles.
                    Please add your new worker from the mobile workers page.
                """)),
            })
        return self.render_json_response({
            "status": status,
            "form_html": render_to_string(self.template_name, {
                'form': self.new_commcare_user_form,
                'data_fields_form': self.custom_data.form,
            }, request=self.request)
        })

    def get(self, request, *args, **kwargs):
        return self.render_form("success")

    @property
    @memoized
    def custom_data(self):
        return CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            post_dict=self.request.POST if self.request.method == "POST" else None,
        )

    @property
    @memoized
    def new_commcare_user_form(self):
        if self.request.method == "POST":
            data = self.request.POST.dict()
            form = CommCareAccountForm(data, domain=self.domain)
        else:
            form = CommCareAccountForm(domain=self.domain)
        return form

    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def post(self, request, *args, **kwargs):
        if self.new_commcare_user_form.is_valid() and self.custom_data.is_valid():
            username = self.new_commcare_user_form.cleaned_data['username']
            password = self.new_commcare_user_form.cleaned_data['password_1']
            phone_number = self.new_commcare_user_form.cleaned_data['phone_number']

            user = CommCareUser.create(
                self.domain,
                username,
                password,
                created_by=request.couch_user,
                created_via=USER_CHANGE_VIA_WEB,
                phone_number=phone_number,
                device_id="Generated from HQ",
                user_data=self.custom_data.get_data_to_save(),
            )

            if 'location_id' in request.GET:
                try:
                    loc = SQLLocation.objects.get(domain=self.domain,
                                                  location_id=request.GET['location_id'])
                except SQLLocation.DoesNotExist:
                    raise Http404()
                user.set_location(loc)

            if phone_number:
                initiate_sms_verification_workflow(user, phone_number)

            user_json = {'user_id': user._id, 'text': user.username_in_report}
            return self.render_json_response({"status": "success",
                                              "user": user_json})
        return self.render_form("failure")


def get_user_upload_context(domain, request_params, download_url, adjective, plural_noun):
    context = {
        'bulk_upload': {
            "help_site": {
                "address": BULK_MOBILE_HELP_SITE,
                "name": _("CommCare Help Site"),
            },
            "download_url": reverse(download_url, args=(domain,)),
            "adjective": _(adjective),
            "plural_noun": _(plural_noun),
        },
        'show_secret_settings': request_params.get("secret", False),
    }
    context.update({
        'bulk_upload_form': get_bulk_upload_form(context),
    })
    return context


class UploadCommCareUsers(BaseUploadUser):
    template_name = 'hqwebapp/bulk_upload.html'
    urlname = 'upload_commcare_users'
    page_title = gettext_noop("Bulk Upload Mobile Workers")
    is_web_upload = False

    @method_decorator(require_can_edit_commcare_users)
    @method_decorator(requires_privilege_with_fallback(privileges.BULK_USER_MANAGEMENT))
    def dispatch(self, request, *args, **kwargs):
        return super(UploadCommCareUsers, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        request_params = self.request.GET if self.request.method == 'GET' else self.request.POST
        return get_user_upload_context(self.domain, request_params, "download_commcare_users", "mobile worker",
                                       "mobile workers")

    def post(self, request, *args, **kwargs):
        return super(UploadCommCareUsers, self).post(request, *args, **kwargs)


class UserUploadStatusView(BaseManageCommCareUserView):
    urlname = 'user_upload_status'
    page_title = gettext_noop('Mobile Worker Upload Status')

    def get(self, request, *args, **kwargs):
        context = super(UserUploadStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse(CommcareUserUploadJobPollView.urlname, args=[self.domain, kwargs['download_id']]),
            'title': _("Mobile Worker Upload Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
            'next_url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
            'next_url_text': _("Return to manage mobile workers"),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class CommcareUserUploadJobPollView(UserUploadJobPollView):
    urlname = "commcare_user_upload_job_poll"
    on_complete_long = 'Mobile Worker upload has finished'
    user_type = 'mobile users'

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(CommcareUserUploadJobPollView, self).dispatch(request, *args, **kwargs)


@require_can_edit_or_view_commcare_users
@location_safe
def user_download_job_poll(request, domain, download_id, template="hqwebapp/partials/shared_download_status.html"):
    try:
        context = get_download_context(download_id, 'Preparing download')
        context.update({'link_text': _('Download Users')})
    except TaskFailedError as e:
        return HttpResponseServerError(e.errors)
    return render(request, template, context)


@location_safe
class DownloadUsersStatusView(BaseUserSettingsView):
    urlname = 'download_users_status'
    page_title = gettext_noop('Download Users Status')

    @method_decorator(require_can_edit_or_view_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': MobileWorkerListView.page_title,
            'url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
        }]

    def get(self, request, *args, **kwargs):
        context = super(DownloadUsersStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('user_download_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Download Users Status"),
            'progress_text': _("Preparing user download."),
            'error_text': _("There was an unexpected error! Please try again or report an issue."),
            'next_url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
            'next_url_text': _("Go back to Mobile Workers"),
        })
        return render(request, 'hqwebapp/bootstrap3/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class FilteredUserDownload(BaseUserSettingsView):

    def get(self, request, domain, *args, **kwargs):
        form = UserFilterForm(request.GET, domain=domain, couch_user=request.couch_user, user_type=self.user_type)
        # To avoid errors on first page load
        form.empty_permitted = True
        context = self.main_context
        context.update({'form': form, 'count_users_url': reverse(self.count_view, args=[domain])})
        return render(
            request,
            "users/filter_and_download.html",
            context
        )


@location_safe
class FilteredCommCareUserDownload(FilteredUserDownload, BaseManageCommCareUserView):
    page_title = gettext_noop('Filter and Download Mobile Workers')
    urlname = 'filter_and_download_commcare_users'
    user_type = MOBILE_USER_TYPE
    count_view = 'count_commcare_users'

    @method_decorator(require_can_edit_commcare_users)
    def get(self, request, domain, *args, **kwargs):
        return super().get(request, domain, *args, **kwargs)


@method_decorator([require_can_use_filtered_user_download], name='dispatch')
class FilteredWebUserDownload(FilteredUserDownload, BaseManageWebUserView):
    page_title = gettext_noop('Filter and Download Users')
    urlname = 'filter_and_download_web_users'
    user_type = WEB_USER_TYPE
    count_view = 'count_web_users'

    @method_decorator(require_can_edit_web_users)
    def get(self, request, domain, *args, **kwargs):
        return super().get(request, domain, *args, **kwargs)


class UsernameUploadMixin(object):
    """
    Contains helper functions for working with a file that consists of a single column of usernames.
    """

    def _get_usernames(self, request):
        """
            Get username list from Excel supplied in request.FILES.
            Adds any errors to request.messages.
        """
        sheet = self._get_sheet(request)
        if not sheet:
            return None

        try:
            usernames = [format_username(row['username'], request.domain) for row in sheet]
        except KeyError:
            messages.error(request, _("No users found. Please check your file contains a 'username' column."))
            return None

        if not len(usernames):
            messages.error(request, _("No users found. Please check file is not empty."))
            return None

        return usernames

    def _get_sheet(self, request):
        try:
            workbook = get_workbook(request.FILES.get('bulk_upload_file'))
        except WorkbookJSONError as e:
            messages.error(request, str(e))
            return None

        try:
            sheet = workbook.get_worksheet()
        except WorksheetNotFound:
            messages.error(request, _("Workbook has no worksheets"))
            return None

        return sheet


class DeleteCommCareUsers(BaseManageCommCareUserView, UsernameUploadMixin):
    urlname = 'delete_commcare_users'
    page_title = gettext_noop('Bulk Delete')
    template_name = 'users/bulk_delete.html'

    @property
    def page_context(self):
        context = self.main_context
        context.update({
            'bulk_upload_form': get_bulk_upload_form(),
        })
        return context

    def post(self, request, *args, **kwargs):
        usernames = self._get_usernames(request)
        if not usernames:
            return self.get(request, *args, **kwargs)

        user_docs_by_id = {doc['_id']: doc for doc in get_user_docs_by_username(usernames)}
        user_ids_with_forms = self._get_user_ids_with_forms(request, user_docs_by_id)
        usernames_not_found = self._get_usernames_not_found(request, user_docs_by_id, usernames)

        if user_ids_with_forms or usernames_not_found:
            messages.error(request, _("""
                No users deleted. Please address the above issue(s) and re-upload your updated file.
            """))
        else:
            self._delete_users(request, user_docs_by_id, user_ids_with_forms)

        return self.get(request, *args, **kwargs)

    def _get_user_ids_with_forms(self, request, user_docs_by_id):
        """
            Find users who have ever submitted a form, and add to request.messages if so.
        """
        user_ids_with_forms = (
            FormES()
            .domain(request.domain)
            .user_id(list(user_docs_by_id))
            .terms_aggregation('form.meta.userID', 'user_id')
        ).run().aggregations.user_id.keys

        if user_ids_with_forms:
            message = _("""
                The following users have form submissions and must be deleted individually: {}.
            """).format(", ".join([raw_username(user_docs_by_id[user_id]['username'])
                                   for user_id in user_ids_with_forms]))
            messages.error(request, message)

        return user_ids_with_forms

    def _get_usernames_not_found(self, request, user_docs_by_id, usernames):
        """
            The only side effect of this is to possibly add to request.messages.
        """
        usernames_not_found = set(usernames) - {doc['username'] for doc in user_docs_by_id.values()}
        if usernames_not_found:
            message = _("The following users were not found: {}.").format(
                ", ".join(map(raw_username, usernames_not_found)))
            messages.error(request, message)
        return usernames_not_found

    def _delete_users(self, request, user_docs_by_id, user_ids_with_forms):
        deleted_count = 0
        for user_id, doc in user_docs_by_id.items():
            if user_id not in user_ids_with_forms:
                CommCareUser.wrap(doc).delete(request.domain, deleted_by=request.couch_user,
                                              deleted_via=USER_CHANGE_VIA_BULK_IMPORTER)
                deleted_count += 1
        if deleted_count:
            messages.success(request, f"{deleted_count} user(s) deleted.")


@method_decorator([toggles.CLEAR_MOBILE_WORKER_DATA.required_decorator()], name='dispatch')
class ClearCommCareUsers(DeleteCommCareUsers):
    urlname = 'clear_commcare_users'
    page_title = gettext_noop('Bulk Clear')
    template_name = 'users/bulk_clear.html'

    def post(self, request, *args, **kwargs):
        usernames = self._get_usernames(request)
        if not usernames:
            return self.get(request, *args, **kwargs)

        user_docs_by_id = {doc['_id']: doc for doc in get_user_docs_by_username(usernames)}
        usernames_not_found = self._get_usernames_not_found(request, user_docs_by_id, usernames)

        if usernames_not_found:
            messages.error(request, _("""
                No users cleared. Please address the above issue(s) and re-upload your updated file.
            """))
        else:
            self._clear_users_data(request, user_docs_by_id)

        return self.get(request, *args, **kwargs)

    def _clear_users_data(self, request, user_docs_by_id):
        from corehq.apps.users.model_log import UserModelAction
        from corehq.apps.hqwebapp.tasks import send_mail_async

        cleared_count = 0
        for user_id, doc in user_docs_by_id.items():
            user = CommCareUser.wrap(doc)
            user.delete_user_data()

            log_user_change(
                by_domain=self.domain,
                for_domain=self.domain,
                couch_user=user,
                changed_by_user=request.couch_user,
                changed_via="web",
                action=UserModelAction.CLEAR
            )

            cleared_count += 1
        if cleared_count:
            messages.success(request, f"{cleared_count} user(s) cleared.")

        send_mail_async.delay(
            subject=f"Mobile Worker Clearing Complete - {self.domain}",
            message=f"The mobile workers have been cleared successfully for the project '{self.domain}'.",
            recipient_list=[self.request.couch_user.get_email()],
            domain=self.domain,
            use_domain_gateway=True,
        )


class CommCareUsersLookup(BaseManageCommCareUserView, UsernameUploadMixin):
    urlname = 'commcare_users_lookup'
    page_title = gettext_noop('Mobile Workers Bulk Lookup')
    template_name = 'users/bulk_lookup.html'

    @property
    def page_context(self):
        context = self.main_context
        context.update({
            'bulk_upload_form': get_bulk_upload_form(),
        })
        return context

    def post(self, request, *args, **kwargs):
        usernames = self._get_usernames(request)
        if not usernames:
            return self.get(request, *args, **kwargs)

        docs_by_username = {doc['username']: doc for doc in get_user_docs_by_username(usernames)}
        rows = []
        for username in usernames:
            row = [raw_username(username)]
            if username in docs_by_username:
                row.extend([_("yes"), docs_by_username[username].get("is_active")])
            else:
                row.extend([_("no"), ""])
            rows.append(row)

        response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
        response['Content-Disposition'] = f'attachment; filename="{self.domain} users.xlsx"'
        response.write(self._excel_data(rows))
        return response

    def _excel_data(self, rows):
        outfile = io.BytesIO()
        tab_name = "users"
        header_table = [(tab_name, [(_("username"), _("exists"), _("is_active"))])]
        writer = Excel2007ExportWriter()
        writer.open(header_table=header_table, file=outfile)
        writer.write([(tab_name, rows)])
        writer.close()
        return outfile.getvalue()


@require_can_edit_commcare_users
@location_safe
def count_commcare_users(request, domain):
    return _count_users(request, domain, MOBILE_USER_TYPE)


@require_can_edit_web_users
@require_can_use_filtered_user_download
def count_web_users(request, domain):
    return _count_users(request, domain, WEB_USER_TYPE)


@login_and_domain_required
def _count_users(request, domain, user_type):
    if user_type not in [MOBILE_USER_TYPE, WEB_USER_TYPE]:
        raise AssertionError(f"Invalid user type for _count_users: {user_type}")

    from corehq.apps.users.dbaccessors import (
        count_invitations_by_filters,
        count_mobile_users_by_filters,
        count_web_users_by_filters,
    )
    form = UserFilterForm(request.GET, domain=domain, couch_user=request.couch_user, user_type=user_type)

    if form.is_valid():
        user_filters = form.cleaned_data
    else:
        return HttpResponseBadRequest("Invalid Request")

    user_count = 0
    group_count = 0
    (is_cross_domain, domains_list) = get_domains_from_user_filters(domain, user_filters)
    for current_domain in domains_list:
        if user_type == MOBILE_USER_TYPE:
            user_count += count_mobile_users_by_filters(current_domain, user_filters)
            group_count += len(load_memoizer(current_domain).groups)
        else:
            user_count += count_web_users_by_filters(current_domain, user_filters)
            user_count += count_invitations_by_filters(current_domain, user_filters)

    return JsonResponse({
        'user_count': user_count,
        'group_count': group_count,
    })


@require_can_edit_or_view_commcare_users
@location_safe
def download_commcare_users(request, domain):
    return download_users(request, domain, user_type=MOBILE_USER_TYPE)


@login_and_domain_required
def download_users(request, domain, user_type):
    if user_type not in [MOBILE_USER_TYPE, WEB_USER_TYPE]:
        raise AssertionError(f"Invalid user type for download_users: {user_type}")

    form = UserFilterForm(request.GET, domain=domain, couch_user=request.couch_user, user_type=user_type)
    if form.is_valid():
        user_filters = form.cleaned_data
    else:
        view = FilteredCommCareUserDownload if user_type == MOBILE_USER_TYPE else FilteredWebUserDownload
        return HttpResponseRedirect(reverse(view, args=[domain]) + "?" + request.GET.urlencode())
    download = DownloadBase()
    if form.cleaned_data['domains'] != [domain]:  # if additional domains added for download
        track_workflow(request.couch_user.username, f'Domain filter used for {user_type} download')
    if form.cleaned_data['columns'] == UserFilterForm.USERNAMES_COLUMN_OPTION:
        if user_type != MOBILE_USER_TYPE:
            raise AssertionError("USERNAME_COLUMN_OPTION only available for mobile users")
        res = bulk_download_usernames_async.delay(domain, download.download_id, user_filters,
                                                  owner_id=request.couch_user.get_id)
    else:
        res = bulk_download_users_async.delay(domain, download.download_id, user_filters,
                                              (user_type == WEB_USER_TYPE), owner_id=request.couch_user.get_id)
    download.set_task(res)
    if user_type == MOBILE_USER_TYPE:
        view = DownloadUsersStatusView
    else:
        from corehq.apps.users.views import DownloadWebUsersStatusView
        view = DownloadWebUsersStatusView
    return redirect(view.urlname, domain, download.download_id)


@location_safe
class CommCareUserConfirmAccountView(TemplateView, DomainViewMixin):
    template_name = "users/commcare_user_confirm_account.html"
    urlname = "commcare_user_confirm_account"
    strict_domain_fetching = True

    @toggles.any_toggle_enabled(toggles.TWO_STAGE_USER_PROVISIONING_BY_SMS, toggles.TWO_STAGE_USER_PROVISIONING)
    def dispatch(self, request, *args, **kwargs):
        return super(CommCareUserConfirmAccountView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def user_id(self):
        return self.kwargs.get('user_id')

    @property
    @memoized
    def user(self):
        return get_document_or_404(CommCareUser, self.domain, self.user_id)

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return MobileWorkerAccountConfirmationForm(self.request.POST)
        else:
            return MobileWorkerAccountConfirmationForm(initial={
                'username': self.user.raw_username,
                'full_name': self.user.full_name,
                'email': self.user.email,
            })

    def get_context_data(self, **kwargs):
        context = super(CommCareUserConfirmAccountView, self).get_context_data(**kwargs)
        context.update({
            'domain_name': self.domain_object.display_name(),
            'user': self.user,
            'form': self.form,
            'button_label': _('Confirm Account')
        })
        return context

    def post(self, request, *args, **kwargs):
        form = self.form
        if form.is_valid():
            user = self.user
            user.email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            user.first_name = full_name[0]
            user.last_name = full_name[1]
            user.confirm_account(password=self.form.cleaned_data['password'])
            messages.success(request, _(
                f'You have successfully confirmed the {user.raw_username} account. '
                'You can now login'
            ))
            if hasattr(self, 'send_success_sms'):
                self.send_success_sms()
            return HttpResponseRedirect('{}?username={}'.format(
                reverse('domain_login', args=[self.domain]),
                user.raw_username,
            ))

        # todo: process form data and activate the account
        return self.get(request, *args, **kwargs)


@location_safe
class CommCareUserConfirmAccountBySMSView(CommCareUserConfirmAccountView):
    urlname = "commcare_user_confirm_account_sms"
    one_day_in_seconds = 60 * 60 * 24

    @property
    @memoized
    def user_invite_hash(self):
        return json.loads(b64_aes_decrypt(self.kwargs.get('user_invite_hash')))

    @property
    @memoized
    def user_id(self):
        return self.user_invite_hash.get('user_id')

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return MobileWorkerAccountConfirmationBySMSForm(self.request.POST)
        else:
            return MobileWorkerAccountConfirmationBySMSForm(initial={
                'username': self.user.raw_username,
                'full_name': self.user.full_name,
                'email': "",
            })

    def get_context_data(self, **kwargs):
        context = super(CommCareUserConfirmAccountBySMSView, self).get_context_data(**kwargs)
        context.update({
            'invite_expired': self.is_invite_valid() is False,
        })
        return context

    def send_success_sms(self):
        settings = SMSAccountConfirmationSettings.get_settings(self.user.domain)
        template_params = {
            'name': self.user.full_name,
            'domain': self.user.domain,
            'username': self.user.raw_username,
            'hq_name': settings.project_name
        }
        lang = guess_domain_language_for_sms(self.user.domain)
        with override(lang):
            text_content = render_to_string(
                "registration/mobile/mobile_worker_account_confirmation_success_sms.txt", template_params
            )
        send_sms(
            domain=self.user.domain, contact=None, phone_number=self.user.default_phone_number, text=text_content
        )

    def is_invite_valid(self):
        hours_elapsed = float(int(time.time()) - self.user_invite_hash.get('time')) / self.one_day_in_seconds
        settings_obj = SMSAccountConfirmationSettings.get_settings(self.user.domain)
        if hours_elapsed <= settings_obj.confirmation_link_expiry_time:
            return True
        return False


@csrf_exempt
@require_POST
@login_or_basic_ex(allow_cc_users=True)
def link_connectid_user(request, domain):
    token = request.POST.get("token")
    if token is None:
        return HttpResponseBadRequest("Token Required")
    connectid_username = get_connectid_userinfo(token)
    link, new = ConnectIDUserLink.objects.get_or_create(
        connectid_username=connectid_username, commcare_user=request.user, domain=request.domain
    )
    if new:
        return HttpResponse(status=201)
    else:
        return HttpResponse()
