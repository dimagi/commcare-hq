from __future__ import absolute_import
from __future__ import unicode_literals
import csv342 as csv
import io
import json
from collections import defaultdict
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.http.response import HttpResponseServerError
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import View, TemplateView

from braces.views import JsonRequestResponseMixin
from couchdbkit import ResourceNotFound
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
import re

from memoized import memoized

from corehq.apps.hqwebapp.crispy import make_form_readonly
from dimagi.utils.web import json_response
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, expose_cached_download

from corehq import privileges
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    EntryPoint,
)
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.custom_data_fields.edit_entity import CustomDataEditor
from corehq.apps.custom_data_fields.models import CUSTOM_DATA_FIELD_PREFIX
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.views.base import DomainViewMixin
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.permissions import location_safe, user_can_access_location_id
from corehq.apps.ota.utils import turn_off_demo_mode, demo_restore_date_created
from corehq.apps.sms.models import SelfRegistrationInvitation
from corehq.apps.sms.verify import initiate_sms_verification_workflow
from corehq.apps.hqwebapp.decorators import use_multiselect
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.apps.users.bulkupload import (
    check_duplicate_usernames,
    check_existing_usernames,
    check_headers,
    UserUploadError,
)
from corehq.apps.users.dbaccessors.all_commcare_users import user_exists
from corehq.apps.users.decorators import (
    require_can_edit_commcare_users,
    require_can_edit_or_view_commcare_users,
)
from corehq.apps.users.forms import (
    CommCareAccountForm, CommCareUserFormSet, CommtrackUserForm,
    MultipleSelectionForm, ConfirmExtraUserChargesForm, NewMobileWorkerForm,
    SelfRegistrationForm, SetUserPasswordForm,
    CommCareUserFilterForm
)
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.tasks import bulk_upload_async, turn_on_demo_mode_task, reset_demo_user_restore_task, \
    bulk_download_users_async
from corehq.apps.users.util import can_add_extra_mobile_workers, format_username
from corehq.apps.users.exceptions import InvalidMobileWorkerRequest
from corehq.apps.users.views import BaseUserSettingsView, BaseEditUserView, get_domain_languages
from corehq.const import USER_DATE_FORMAT, GOOGLE_PLAY_STORE_COMMCARE_URL
from corehq.toggles import FILTERED_BULK_USER_DOWNLOAD
from corehq.util.dates import iso_string_to_datetime
from corehq.util.workbook_json.excel import (
    enforce_string_type,
    get_workbook,
    StringTypeRequiredError,
    WorkbookJSONError,
    WorksheetNotFound,
)
from soil import DownloadBase
from .custom_data_fields import UserFieldsView
import six

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
    page_title = ugettext_noop("Edit Mobile Worker")

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
        context.update({
            'edit_user_form_title': self.edit_user_form_title,
            'strong_mobile_passwords': self.request.project.strong_mobile_passwords,
            'implement_password_obfuscation': settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE
        })
        return context

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
        return Group.by_user(self.editable_user)

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
            return CommtrackUserForm(self.request.POST, domain=self.domain)

        # currently only support one location on the UI
        linked_loc = self.editable_user.location
        initial_id = linked_loc._id if linked_loc else None
        program_id = self.editable_user.get_domain_membership(self.domain).program_id
        assigned_locations = self.editable_user.assigned_location_ids
        return CommtrackUserForm(
            domain=self.domain,
            initial={
                'primary_location': initial_id,
                'program_id': program_id,
                'assigned_locations': assigned_locations}
        )

    @property
    def page_context(self):
        from corehq.apps.users.views.mobile import GroupsListView

        if self.request.is_view_only:
            make_form_readonly(self.commtrack_form)
            make_form_readonly(self.form_user_update.user_form)
            make_form_readonly(self.form_user_update.custom_data.form)

        context = {
            'are_groups': bool(len(self.all_groups)),
            'groups_url': reverse('all_groups', args=[self.domain]),
            'group_form': self.group_form,
            'reset_password_form': self.reset_password_form,
            'is_currently_logged_in_user': self.is_currently_logged_in_user,
            'data_fields_form': self.form_user_update.custom_data.form,
            'can_use_inbound_sms': domain_has_privilege(self.domain, privileges.INBOUND_SMS),
            'can_create_groups': (
                self.request.couch_user.has_permission(self.domain, 'edit_groups') and
                self.request.couch_user.has_permission(self.domain, 'access_all_locations')
            ),
            'needs_to_downgrade_locations': (
                users_have_locations(self.domain) and
                not has_privilege(self.request, privileges.LOCATIONS)
            ),
            'demo_restore_date': naturaltime(demo_restore_date_created(self.editable_user)),
            'hide_password_feedback': settings.ENABLE_DRACONIAN_SECURITY_FEATURES,
            'group_names': [g.name for g in self.groups],
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
        return [('none', _('(none)'))] + self.editable_role_choices

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
            editable_user=self.editable_user, request_user=self.request.couch_user)

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
                self.editable_user.add_phone_number(phone_number)
                self.editable_user.save(spawn_task=True)
                messages.success(request, _("Phone number added."))
            else:
                messages.error(request, _("Please enter digits only."))
        return super(EditCommCareUserView, self).post(request, *args, **kwargs)


class ConfirmBillingAccountForExtraUsersView(BaseUserSettingsView, AsyncHandlerMixin):
    urlname = 'extra_users_confirm_billing'
    template_name = 'users/extra_users_confirm_billing.html'
    page_title = ugettext_noop("Confirm Billing Information")
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
    if (user.user_location_id and
            SQLLocation.objects.get_or_None(location_id=user.user_location_id,
                                            user_id=user._id)):
        messages.error(request, _("This is a location user. You must delete the "
                       "corresponding location before you can delete this user."))
        return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]))
    user.retire()
    messages.success(request, "User %s has been deleted. All their submissions and cases will be permanently deleted in the next few minutes" % user.username)
    return HttpResponseRedirect(reverse(MobileWorkerListView.urlname, args=[domain]))


@require_can_edit_commcare_users
@require_POST
def restore_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    success, message = user.unretire()
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
        from corehq.apps.app_manager.views.utils import unset_practice_mode_configured_apps, \
            get_practice_mode_configured_apps
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
    page_title = ugettext_noop("Turn off Demo mode")

    @property
    def page_context(self):
        from corehq.apps.app_manager.views.utils import get_practice_mode_configured_apps
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
    page_title = ugettext_noop('Demo User Status')

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
        return render(request, 'hqwebapp/soil_status_full.html', context)

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
        assert user.doc_type == "CommCareUser"
        assert user.domain == domain
        user.set_groups(form.cleaned_data['selected_ids'])
        messages.success(request, _("User groups updated!"))
    else:
        messages.error(request, _("Form not valid. A group may have been deleted while you were viewing this page"
                                  "Please try again."))
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id]))


@require_can_edit_commcare_users
@require_POST
def update_user_data(request, domain, couch_user_id):
    user_data = request.POST["user-data"]
    if user_data:
        updated_data = json.loads(user_data)
        user = CommCareUser.get(couch_user_id)
        assert user.doc_type == "CommCareUser"
        assert user.domain == domain
        user.user_data = updated_data
        user.save(spawn_task=True)
    messages.success(request, "User data updated!")
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id]))


@location_safe
class MobileWorkerListView(JSONResponseMixin, BaseUserSettingsView):
    template_name = 'users/mobile_workers.html'
    urlname = 'mobile_workers'
    page_title = ugettext_noop("Mobile Workers")

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
    def _mobile_worker_form(self):
        return self.new_mobile_worker_form

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
    def page_context(self):
        if FILTERED_BULK_USER_DOWNLOAD.enabled(self.domain):
            bulk_download_url = reverse(FilteredUserDownload.urlname, args=[self.domain])
        else:
            bulk_download_url = reverse("download_commcare_users", args=[self.domain])
        return {
            'new_mobile_worker_form': self.new_mobile_worker_form,
            'custom_fields_form': self.custom_data.form,
            'custom_field_slugs': [f.slug for f in self.custom_data.fields],
            'can_bulk_edit_users': self.can_bulk_edit_users,
            'can_add_extra_users': self.can_add_extra_users,
            'can_access_all_locations': self.can_access_all_locations,
            'draconian_security': settings.ENABLE_DRACONIAN_SECURITY_FEATURES,
            'pagination_limit_cookie_name': (
                'hq.pagination.limit.mobile_workers_list.%s' % self.domain),
            'can_edit_billing_info': self.request.couch_user.is_domain_admin(self.domain),
            'strong_mobile_passwords': self.request.project.strong_mobile_passwords,
            'implement_password_obfuscation': settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE,
            'bulk_download_url': bulk_download_url
        }

    @property
    @memoized
    def query(self):
        return self.request.GET.get('query')

    @allow_remote_invocation
    def check_username(self, in_data):
        try:
            username = in_data['username'].strip()
        except KeyError:
            return HttpResponseBadRequest('You must specify a username')
        if username == 'admin' or username == 'demo_user':
            return {'error': _('Username {} is reserved.').format(username)}
        try:
            validate_email("{}@example.com".format(username))
            if BAD_MOBILE_USERNAME_REGEX.search(username) is not None:
                raise ValidationError("Username contained an invalid character")
        except ValidationError:
            if '..' in username:
                return {
                    'error': _("Username may not contain consecutive . (period).")
                }
            if username.endswith('.'):
                return {
                    'error': _("Username may not end with a . (period).")
                }
            return {
                'error': _("Username may not contain special characters.")
            }

        full_username = format_username(username, self.domain)
        exists = user_exists(full_username)
        if exists.exists:
            if exists.is_deleted:
                result = {'warning': _('Username {} belonged to a user that was deleted.'
                                       ' Reusing it may have unexpected consequences.').format(username)}
            else:
                result = {'error': _('Username {} is already taken').format(username)}
        else:
            result = {'success': _('Username {} is available').format(username)}
        return result

    @allow_remote_invocation
    def create_mobile_worker(self, in_data):
        if self.request.is_view_only:
            return {
                'error': _("You do not have permission to create mobile workers.")
            }

        try:
            self._ensure_proper_request(in_data)
            form_data = self._construct_form_data(in_data)
        except InvalidMobileWorkerRequest as e:
            return {
                'error': six.text_type(e)
            }

        self.request.POST = form_data

        is_valid = lambda: self._mobile_worker_form.is_valid() and self.custom_data.is_valid()
        if not is_valid():
            return {'error': _("Forms did not validate")}

        couch_user = self._build_commcare_user()

        return {
            'success': True,
            'user_id': couch_user.userID,
        }

    def _build_commcare_user(self):
        username = self.new_mobile_worker_form.cleaned_data['username']
        password = self.new_mobile_worker_form.cleaned_data['new_password']
        first_name = self.new_mobile_worker_form.cleaned_data['first_name']
        last_name = self.new_mobile_worker_form.cleaned_data['last_name']
        location_id = self.new_mobile_worker_form.cleaned_data['location_id']

        return CommCareUser.create(
            self.domain,
            username,
            password,
            device_id="Generated from HQ",
            first_name=first_name,
            last_name=last_name,
            user_data=self.custom_data.get_data_to_save(),
            location=SQLLocation.objects.get(location_id=location_id) if location_id else None,
        )

    def _ensure_proper_request(self, in_data):
        if not self.can_add_extra_users:
            raise InvalidMobileWorkerRequest(_("No Permission."))

        if 'user' not in in_data:
            raise InvalidMobileWorkerRequest(_("Please provide mobile worker data."))

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
                'domain': self.domain,
            }
            for k, v in user_data.get('custom_fields', {}).items():
                form_data["{}-{}".format(CUSTOM_DATA_FIELD_PREFIX, k)] = v
            return form_data
        except Exception as e:
            raise InvalidMobileWorkerRequest(_("Check your request: {}".format(e)))


@require_can_edit_commcare_users
@require_POST
def activate_commcare_user(request, domain, user_id):
    return _modify_user_status(request, domain, user_id, True)


@require_can_edit_commcare_users
@require_POST
def deactivate_commcare_user(request, domain, user_id):
    return _modify_user_status(request, domain, user_id, False)


def _modify_user_status(request, domain, user_id, is_active):
    user = CommCareUser.get_by_user_id(user_id, domain)
    if (not _can_edit_workers_location(request.couch_user, user)
            or (is_active and not can_add_extra_mobile_workers(request))):
        return json_response({
            'error': _("No Permission."),
        })
    if not is_active and user.user_location_id:
        return json_response({
            'error': _("This is a location user, archive or delete the "
                       "corresponding location to deactivate it."),
        })
    user.is_active = is_active
    user.save(spawn_task=True)
    return json_response({
        'success': True,
    })


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
    ]).run()
    users = users_data.hits

    for user in users:
        date_registered = user.pop('created_on', '')
        if date_registered:
            date_registered = iso_string_to_datetime(date_registered).strftime(USER_DATE_FORMAT)
        user.update({
            'username': user.pop('base_username', ''),
            'user_id': user.pop('_id'),
            'date_registered': date_registered,
        })

    return json_response({
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


class UploadCommCareUsers(BaseManageCommCareUserView):
    template_name = 'hqwebapp/bulk_upload.html'
    urlname = 'upload_commcare_users'
    page_title = ugettext_noop("Bulk Upload Mobile Workers")

    @method_decorator(requires_privilege_with_fallback(privileges.BULK_USER_MANAGEMENT))
    def dispatch(self, request, *args, **kwargs):
        return super(UploadCommCareUsers, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        request_params = self.request.GET if self.request.method == 'GET' else self.request.POST
        context = {
            'bulk_upload': {
                "help_site": {
                    "address": BULK_MOBILE_HELP_SITE,
                    "name": _("CommCare Help Site"),
                },
                "download_url": reverse(
                    "download_commcare_users", args=(self.domain,)),
                "adjective": _("mobile worker"),
                "plural_noun": _("mobile workers"),
            },
            'show_secret_settings': request_params.get("secret", False),
        }
        context.update({
            'bulk_upload_form': get_bulk_upload_form(context),
        })
        return context

    def post(self, request, *args, **kwargs):
        """View's dispatch method automatically calls this"""
        try:
            self.workbook = get_workbook(request.FILES.get('bulk_upload_file'))
        except WorkbookJSONError as e:
            messages.error(request, six.text_type(e))
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
            check_headers(self.user_specs)
        except UserUploadError as e:
            messages.error(request, _(six.text_type(e)))
            return HttpResponseRedirect(reverse(UploadCommCareUsers.urlname, args=[self.domain]))

        # convert to list here because iterator destroys the row once it has
        # been read the first time
        self.user_specs = list(self.user_specs)

        for user_spec in self.user_specs:
            try:
                user_spec['username'] = enforce_string_type(user_spec['username'])
            except StringTypeRequiredError:
                messages.error(
                    request,
                    _("Error: Expected username to be a Text type for username {0}")
                    .format(user_spec['username'])
                )
                return HttpResponseRedirect(reverse(UploadCommCareUsers.urlname, args=[self.domain]))

        try:
            check_existing_usernames(self.user_specs, self.domain)
        except UserUploadError as e:
            messages.error(request, _(six.text_type(e)))
            return HttpResponseRedirect(reverse(UploadCommCareUsers.urlname, args=[self.domain]))

        try:
            check_duplicate_usernames(self.user_specs)
        except UserUploadError as e:
            messages.error(request, _(six.text_type(e)))
            return HttpResponseRedirect(reverse(UploadCommCareUsers.urlname, args=[self.domain]))

        task_ref = expose_cached_download(payload=None, expiry=1*60*60, file_extension=None)
        task = bulk_upload_async.delay(
            self.domain,
            self.user_specs,
            list(self.group_specs),
        )
        task_ref.set_task(task)
        return HttpResponseRedirect(
            reverse(
                UserUploadStatusView.urlname,
                args=[self.domain, task_ref.download_id]
            )
        )


class UserUploadStatusView(BaseManageCommCareUserView):
    urlname = 'user_upload_status'
    page_title = ugettext_noop('Mobile Worker Upload Status')

    def get(self, request, *args, **kwargs):
        context = super(UserUploadStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('user_upload_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Mobile Worker Upload Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
            'next_url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
            'next_url_text': _("Return to manage mobile workers"),
        })
        return render(request, 'hqwebapp/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_commcare_users
def user_upload_job_poll(request, domain, download_id, template="users/mobile/partials/user_upload_status.html"):
    try:
        context = get_download_context(download_id)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': _('Bulk upload complete.'),
        'on_complete_long': _('Mobile Worker upload has finished'),

    })

    class _BulkUploadResponseWrapper(object):

        def __init__(self, context):
            results = context.get('result') or defaultdict(lambda: [])
            self.response_rows = results['rows']
            self.response_errors = results['errors']
            self.problem_rows = [r for r in self.response_rows if r['flag'] not in ('updated', 'created')]

        def success_count(self):
            return len(self.response_rows) - len(self.problem_rows)

        def has_errors(self):
            return bool(self.response_errors or self.problem_rows)

        def errors(self):
            errors = []
            for row in self.problem_rows:
                if row['flag'] == 'missing-data':
                    errors.append(_('A row with no username was skipped'))
                else:
                    errors.append('{username}: {flag}'.format(**row))
            errors.extend(self.response_errors)
            return errors

    context['result'] = _BulkUploadResponseWrapper(context)
    return render(request, template, context)



@require_can_edit_commcare_users
def user_download_job_poll(request, domain, download_id, template="hqwebapp/partials/shared_download_status.html"):
    try:
        context = get_download_context(download_id, 'Preparing download')
        context.update({'link_text': _('Download Users')})
    except TaskFailedError as e:
        return HttpResponseServerError(e.errors)
    return render(request, template, context)


class DownloadUsersStatusView(BaseManageCommCareUserView):
    urlname = 'download_users_status'
    page_title = ugettext_noop('Download Users Status')

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
        return render(request, 'hqwebapp/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


class FilteredUserDownload(BaseManageCommCareUserView):
    urlname = 'filter_and_download_commcare_users'
    page_title = ugettext_noop('Filter and Download')

    @method_decorator(require_can_edit_commcare_users)
    def get(self, request, domain, *args, **kwargs):
        form = CommCareUserFilterForm(request.GET, domain=domain)
        context = self.main_context
        context.update({'form': form, 'count_users_url': reverse('count_users', args=[domain])})
        return render(
            request,
            "users/filter_and_download.html",
            context
        )


@require_can_edit_commcare_users
def count_users(request, domain):
    from corehq.apps.users.dbaccessors.all_commcare_users import get_commcare_users_by_filters
    form = CommCareUserFilterForm(request.GET, domain=domain)
    user_filters = {}
    if form.is_valid():
        user_filters = form.cleaned_data
    else:
        return HttpResponseBadRequest("Invalid Request")

    return json_response({
        'count': get_commcare_users_by_filters(domain, user_filters, count_only=True)
    })


@require_can_edit_commcare_users
def download_commcare_users(request, domain):
    form = CommCareUserFilterForm(request.GET, domain=domain)
    user_filters = {}
    if form.is_valid():
        user_filters = form.cleaned_data
    else:
        return HttpResponseRedirect(
            reverse(FilteredUserDownload.urlname, args=[domain]) + "?" + request.GET.urlencode())
    download = DownloadBase()
    res = bulk_download_users_async.delay(domain, download.download_id, user_filters)
    download.set_task(res)
    return redirect(DownloadUsersStatusView.urlname, domain, download.download_id)


class CommCareUserSelfRegistrationView(TemplateView, DomainViewMixin):
    template_name = "users/mobile/commcare_user_self_register.html"
    urlname = "commcare_user_self_register"
    strict_domain_fetching = True

    @property
    @memoized
    def token(self):
        return self.kwargs.get('token')

    @property
    @memoized
    def invitation(self):
        return SelfRegistrationInvitation.by_token(self.token)

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return SelfRegistrationForm(self.request.POST, domain=self.domain,
                require_email=self.invitation.require_email)
        else:
            return SelfRegistrationForm(domain=self.domain,
                require_email=self.invitation.require_email)

    def get_context_data(self, **kwargs):
        context = super(CommCareUserSelfRegistrationView, self).get_context_data(**kwargs)
        context.update({
            'hr_name': self.domain_object.display_name(),
            'form': self.form,
            'invitation': self.invitation,
            'can_add_extra_mobile_workers': can_add_extra_mobile_workers(self.request),
            'google_play_store_url': GOOGLE_PLAY_STORE_COMMCARE_URL,
        })
        return context

    def validate_request(self):
        if (
            not self.invitation or
            self.invitation.domain != self.domain or
            not self.domain_object.sms_mobile_worker_registration_enabled
        ):
            raise Http404()

    def get(self, request, *args, **kwargs):
        self.validate_request()
        return super(CommCareUserSelfRegistrationView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.validate_request()
        if (
            not self.invitation.expired and
            not self.invitation.already_registered and
            self.form.is_valid()
        ):
            email = self.form.cleaned_data.get('email')
            if email:
                email = email.lower()

            user = CommCareUser.create(
                self.domain,
                self.form.cleaned_data.get('username'),
                self.form.cleaned_data.get('password'),
                email=email,
                phone_number=self.invitation.phone_number,
                device_id='Generated from HQ',
                user_data=self.invitation.custom_user_data,
            )
            # Since the user is being created by following the link and token
            # we sent to their phone by SMS, we can verify their phone number
            entry = user.get_or_create_phone_entry(self.invitation.phone_number)
            entry.set_two_way()
            entry.set_verified()
            entry.save()

            self.invitation.registered_date = datetime.utcnow()
            self.invitation.save()
        return self.get(request, *args, **kwargs)
