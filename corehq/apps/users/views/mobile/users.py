import csv
import io
import json
from collections import defaultdict
from datetime import datetime
from zipfile import BadZipfile

from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseBadRequest, Http404
from django.http.response import HttpResponseServerError
from django.shortcuts import render, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST
from django.views.generic import View, TemplateView

from braces.views import JsonRequestResponseMixin
from couchdbkit import ResourceNotFound
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from openpyxl.utils.exceptions import InvalidFileException
import re

from couchexport.models import Format
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
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
from corehq.apps.custom_data_fields import CustomDataEditor
from corehq.apps.custom_data_fields.models import CUSTOM_DATA_FIELD_PREFIX
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.locations.models import Location
from corehq.apps.ota.utils import turn_off_demo_mode
from corehq.apps.sms.models import SelfRegistrationInvitation
from corehq.apps.sms.verify import initiate_sms_verification_workflow
from corehq.apps.style.decorators import (
    use_bootstrap3,
    use_select2,
    use_angular_js,
    use_multiselect,
)
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.apps.users.bulkupload import check_headers, dump_users_and_groups, GroupNameError, UserUploadError
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.forms import (
    CommCareAccountForm, UpdateCommCareUserInfoForm, CommtrackUserForm,
    MultipleSelectionForm, ConfirmExtraUserChargesForm, NewMobileWorkerForm,
    SelfRegistrationForm, SetUserPasswordForm,
)
from corehq.apps.users.models import CommCareUser, UserRole, CouchUser
from corehq.apps.users.tasks import bulk_upload_async, turn_on_demo_mode_task, reset_demo_user_restore_task
from corehq.apps.users.util import can_add_extra_mobile_workers, format_username
from corehq.apps.users.views import BaseUserSettingsView, BaseEditUserView, get_domain_languages
from corehq.const import USER_DATE_FORMAT
from corehq.util.couch import get_document_or_404
from corehq.util.spreadsheets.excel import JSONReaderError, HeaderValueError, \
    WorksheetNotFound, WorkbookJSONReader
from soil import DownloadBase
from .custom_data_fields import UserFieldsView

BULK_MOBILE_HELP_SITE = ("https://confluence.dimagi.com/display/commcarepublic"
                         "/Create+and+Manage+CommCare+Mobile+Workers#Createand"
                         "ManageCommCareMobileWorkers-B.UseBulkUploadtocreatem"
                         "ultipleusersatonce")
DEFAULT_USER_LIST_LIMIT = 10


class EditCommCareUserView(BaseEditUserView):
    template_name = "users/edit_commcare_user.html"
    urlname = "edit_commcare_user"
    user_update_form_class = UpdateCommCareUserInfoForm
    page_title = ugettext_noop("Edit Mobile Worker")

    @use_bootstrap3
    @use_multiselect
    @use_select2
    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(EditCommCareUserView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(EditCommCareUserView, self).main_context
        context.update({
            'edit_user_form_title': self.edit_user_form_title,
        })
        return context

    @property
    @memoized
    def custom_data(self):
        is_custom_data_post = self.request.method == "POST" and self.request.POST['form_type'] == "update-user"
        return CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            existing_custom_data=self.editable_user.user_data,
            post_dict=self.request.POST if is_custom_data_post else None,
        )

    @property
    @memoized
    def editable_user(self):
        try:
            user = CommCareUser.get_by_user_id(self.editable_user_id, self.domain)
            if not user or user.is_deleted():
                raise Http404()
            return user
        except (ResourceNotFound, CouchUser.AccountTypeError, KeyError):
            raise Http404()

    @property
    def edit_user_form_title(self):
        return _("Information for %s") % self.editable_user.human_friendly_name

    @property
    def is_currently_logged_in_user(self):
        return self.editable_user_id == self.couch_user._id

    @property
    @memoized
    def reset_password_form(self):
        return SetUserPasswordForm(self.domain, self.editable_user_id, user="")

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
    def update_commtrack_form(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "commtrack":
            return CommtrackUserForm(self.request.POST, domain=self.domain)

        # currently only support one location on the UI
        linked_loc = self.editable_user.location
        initial_id = linked_loc._id if linked_loc else None
        program_id = self.editable_user.get_domain_membership(self.domain).program_id
        return CommtrackUserForm(domain=self.domain, initial={'location': initial_id, 'program_id': program_id})

    @property
    def page_context(self):
        context = {
            'are_groups': bool(len(self.all_groups)),
            'groups_url': reverse('all_groups', args=[self.domain]),
            'group_form': self.group_form,
            'reset_password_form': self.reset_password_form,
            'is_currently_logged_in_user': self.is_currently_logged_in_user,
            'data_fields_form': self.custom_data.form,
            'can_use_inbound_sms': domain_has_privilege(self.domain, privileges.INBOUND_SMS),
            'needs_to_downgrade_locations': (
                users_have_locations(self.domain) and
                not has_privilege(self.request, privileges.LOCATIONS)
            ),
        }
        if self.domain_object.commtrack_enabled or self.domain_object.uses_locations:
            context.update({
                'commtrack_enabled': self.domain_object.commtrack_enabled,
                'uses_locations': self.domain_object.uses_locations,
                'commtrack': {
                    'update_form': self.update_commtrack_form,
                },
            })
        return context

    @property
    def user_role_choices(self):
        return UserRole.commcareuser_role_choices(self.domain)

    @property
    def can_change_user_roles(self):
        return ((self.request.user.is_superuser or self.request.couch_user.can_edit_web_users(domain=self.domain))
                and self.request.couch_user.user_id != self.editable_user_id)

    @property
    def existing_role(self):
        role = self.editable_user.get_role(self.domain)
        if role is None:
            role = "none"
        else:
            role = role.get_qualified_id()
        return role

    @property
    @memoized
    def form_user_update(self):
        form = super(EditCommCareUserView, self).form_user_update
        form.load_language(language_choices=get_domain_languages(self.domain))
        if self.can_change_user_roles:
            form.load_roles(current_role=self.existing_role, role_choices=self.user_role_choices)
        else:
            del form.fields['role']
        return form

    @property
    def parent_pages(self):
        return [{
            'title': MobileWorkerListView.page_title,
            'url': reverse(MobileWorkerListView.urlname, args=[self.domain]),
        }]

    def post(self, request, *args, **kwargs):
        if request.POST['form_type'] == "commtrack":
            if self.update_commtrack_form.is_valid():
                self.update_commtrack_form.save(self.editable_user)
                messages.success(request, _("Information updated!"))
        elif self.request.POST['form_type'] == "add-phonenumber":
            phone_number = self.request.POST['phone_number']
            phone_number = re.sub('\s', '', phone_number)
            if re.match(r'\d+$', phone_number):
                self.editable_user.add_phone_number(phone_number)
                self.editable_user.save()
                messages.success(request, _("Phone number added!"))
            else:
                messages.error(request, _("Please enter digits only."))
        return super(EditCommCareUserView, self).post(request, *args, **kwargs)

    def custom_user_is_valid(self):
        if self.custom_data.is_valid():
            self.editable_user.user_data = self.custom_data.get_data_to_save()
            self.editable_user.save()
            return True
        else:
            return False


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

    @use_select2
    @use_bootstrap3
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


# this was originally written with a GET, which is wrong
# I'm not fixing for now, just adding the require_POST to make it unusable
@require_POST
@require_can_edit_commcare_users
def set_commcare_user_group(request, domain):
    user_id = request.GET.get('user', '')
    user = CommCareUser.get_by_user_id(user_id)
    group_name = request.GET.get('group', '')
    group = Group.by_name(domain, group_name)
    if not user.is_commcare_user() or user.domain != domain or not group:
        return HttpResponseForbidden()
    for group in user.get_case_sharing_groups():
        group.remove_user(user)
    group.add_user(user)
    return HttpResponseRedirect(reverse(MobileWorkerListView.urlname, args=[domain]))


@require_can_edit_commcare_users
def archive_commcare_user(request, domain, user_id, is_active=False):
    can_add_extra_users = can_add_extra_mobile_workers(request)
    if not can_add_extra_users and is_active:
        return HttpResponse(json.dumps({
            'success': False,
            'message': _("You are not allowed to add additional mobile workers"),
        }))
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.is_active = is_active
    user.save()
    return HttpResponse(json.dumps(dict(
        success=True,
        message=_("User '{user}' has successfully been {action}.").format(
            user=user.raw_username,
            action=_("Reactivated") if user.is_active else _("Deactivated"),
        )
    )))


@require_can_edit_commcare_users
@require_POST
def delete_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.retire()
    messages.success(request, "User %s has been deleted. All their submissions and cases will be permanently deleted in the next few minutes" % user.username)
    return HttpResponseRedirect(reverse(MobileWorkerListView.urlname, args=[domain]))


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
        res = turn_on_demo_mode_task.delay(user, domain)
        download.set_task(res)
        response = redirect('hq_soil_download', domain, download.download_id)
        response['Location'] += '?next=%s' % (edit_user_url)
        return response
    else:
        turn_off_demo_mode(user)
        messages.success(request, _("Successfully turned off demo mode!"))
    return HttpResponseRedirect(edit_user_url)


@require_can_edit_commcare_users
@require_POST
def reset_demo_user_restore(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    if not user.is_demo_user:
        warning = _("The user is not a demo user.")
        messages.warning(require_POST, warning)
        return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]))

    download = DownloadBase()
    res = reset_demo_user_restore_task.delay(user, domain)
    download.set_task(res)

    response = redirect('hq_soil_download', domain, download.download_id)
    response['Location'] += '?next=%s' % (reverse(EditCommCareUserView.urlname, args=[domain, user_id]))
    return response


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
        user.save()
    messages.success(request, "User data updated!")
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, couch_user_id]))


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


class MobileWorkerListView(JSONResponseMixin, BaseUserSettingsView):
    template_name = 'users/mobile_workers.html'
    urlname = 'mobile_workers'
    page_title = ugettext_noop("Mobile Workers")

    @use_bootstrap3
    @use_select2
    @use_angular_js
    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, *args, **kwargs):
        return super(MobileWorkerListView, self).dispatch(*args, **kwargs)

    @property
    def can_bulk_edit_users(self):
        return has_privilege(self.request, privileges.BULK_USER_MANAGEMENT)

    @property
    def can_add_extra_users(self):
        return can_add_extra_mobile_workers(self.request)

    @property
    @memoized
    def new_mobile_worker_form(self):
        if self.request.method == "POST":
            return NewMobileWorkerForm(self.domain, self.request.POST)
        return NewMobileWorkerForm(self.domain)

    @property
    @memoized
    def custom_data(self):
        return CustomDataEditor(
            field_view=UserFieldsView,
            domain=self.domain,
            post_dict=self.request.POST if self.request.method == "POST" else None,
            required_only=True,
            angular_model="mobileWorker.customFields",
        )

    @property
    def page_context(self):
        return {
            'new_mobile_worker_form': self.new_mobile_worker_form,
            'custom_fields_form': self.custom_data.form,
            'custom_fields': [f.slug for f in self.custom_data.fields],
            'custom_field_names': [f.label for f in self.custom_data.fields],
            'can_bulk_edit_users': self.can_bulk_edit_users,
            'can_add_extra_users': self.can_add_extra_users,
            'pagination_limit_cookie_name': (
                'hq.pagination.limit.mobile_workers_list.%s' % self.domain),
            'can_edit_billing_info': self.request.couch_user.is_domain_admin(self.domain)
        }

    @property
    @memoized
    def query(self):
        return self.request.GET.get('query')

    def _format_user(self, user_json):
        user = CommCareUser.wrap(user_json)
        user_data = {}
        for field in self.custom_data.fields:
            user_data[field.slug] = user.user_data.get(field.slug, '')
        return {
            'username': user.raw_username,
            'customFields': user_data,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phoneNumbers': user.phone_numbers,
            'user_id': user.user_id,
            'mark_activated': False,
            'mark_deactivated': False,
            'dateRegistered': user.created_on.strftime(USER_DATE_FORMAT) if user.created_on else '',
            'editUrl': reverse(EditCommCareUserView.urlname, args=[self.domain, user.user_id]),
            'deactivateUrl': "#",
            'actionText': _("Deactivate") if user.is_active else _("Activate"),
            'action': 'deactivate' if user.is_active else 'activate',
        }

    def _user_query(self, search_string, page, limit):
        user_es = get_search_users_in_domain_es_query(
            domain=self.domain, search_string=search_string,
            offset=page * limit, limit=limit)
        return user_es.mobile_users()

    @allow_remote_invocation
    def get_pagination_data(self, in_data):
        if not isinstance(in_data, dict):
            return {
                'success': False,
                'error': _("Please provide pagination info."),
            }
        try:
            limit = int(in_data.get('limit', 10))
        except ValueError:
            limit = 10

        # front end pages start at one
        page = in_data.get('page', 1)
        query = in_data.get('query')

        # backend pages start at 0
        users_query = self._user_query(query, page - 1, limit)
        if in_data.get('showDeactivatedUsers', False):
            users_query = users_query.show_only_inactive()
        users_data = users_query.run()
        return {
            'response': {
                'itemList': map(self._format_user, users_data.hits),
                'total': users_data.total,
                'page': page,
                'query': query,
            },
            'success': True,
        }

    @allow_remote_invocation
    def modify_user_status(self, in_data):
        try:
            user_id = in_data['user_id']
        except KeyError:
            return {
                'error': _("Please provide a user_id."),
            }
        try:
            is_active = in_data['is_active']
        except KeyError:
            return {
                'error': _("Please provide an is_active status."),
            }
        user = CommCareUser.get_by_user_id(user_id, self.domain)
        if is_active and not self.can_add_extra_users:
            return {
                'error': _("No Permission."),
            }
        user.is_active = is_active
        user.save()
        return {
            'success': True,
        }

    @allow_remote_invocation
    def check_username(self, in_data):
        try:
            username = in_data['username'].strip()
        except KeyError:
            return HttpResponseBadRequest('You must specify a username')
        if username == 'admin' or username == 'demo_user':
            return {'error': _(u'Username {} is reserved.').format(username)}
        if '@' in username:
            return {
                'error': _(u'Username {} cannot contain "@".').format(username)
            }
        if ' ' in username:
            return {
                'error': _(u'Username {} cannot contain '
                           'spaces.').format(username)
            }
        full_username = format_username(username, self.domain)
        if CommCareUser.get_by_username(full_username, strict=True):
            result = {'error': _(u'Username {} is already taken').format(username)}
        else:
            result = {'success': _(u'Username {} is available').format(username)}
        return result

    @allow_remote_invocation
    def create_mobile_worker(self, in_data):
        if not self.can_add_extra_users:
            return {
                'error': _("No Permission."),
            }
        try:
            user_data = in_data['mobileWorker']
        except KeyError:
            return {
                'error': _("Please provide mobile worker data."),
            }

        try:
            form_data = {}
            for k, v in user_data.get('customFields', {}).items():
                form_data["{}-{}".format(CUSTOM_DATA_FIELD_PREFIX, k)] = v
            for f in ['username', 'password', 'first_name', 'last_name']:
                form_data[f] = user_data[f]
            form_data['domain'] = self.domain
            self.request.POST = form_data
        except Exception as e:
            return {
                'error': _("Check your request: %s" % e)
            }

        if self.new_mobile_worker_form.is_valid() and self.custom_data.is_valid():

            username = self.new_mobile_worker_form.cleaned_data['username']
            password = self.new_mobile_worker_form.cleaned_data['password']
            first_name = self.new_mobile_worker_form.cleaned_data['first_name']
            last_name = self.new_mobile_worker_form.cleaned_data['last_name']

            couch_user = CommCareUser.create(
                self.domain,
                format_username(username, self.domain),
                password,
                device_id="Generated from HQ",
                first_name=first_name,
                last_name=last_name,
                user_data=self.custom_data.get_data_to_save(),
            )

            return {
                'success': True,
                'editUrl': reverse(
                    EditCommCareUserView.urlname,
                    args=[self.domain, couch_user.userID]
                )
            }

        return {
            'error': _("Forms did not validate"),
        }


# This is almost entirely a duplicate of CreateCommCareUserView. That view will
# be going away soon, so I didn't bother to abstract out the commonalities.
class CreateCommCareUserModal(JsonRequestResponseMixin, DomainViewMixin, View):
    template_name = "users/new_mobile_worker_modal.html"
    urlname = 'new_mobile_worker_modal'

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        if not can_add_extra_mobile_workers(request):
            raise PermissionDenied()
        return super(CreateCommCareUserModal, self).dispatch(request, *args, **kwargs)

    def render_form(self, status):
        context = RequestContext(self.request, {
            'form': self.new_commcare_user_form,
            'data_fields_form': self.custom_data.form,
        })
        return self.render_json_response({
            "status": status,
            "form_html": render_to_string(self.template_name, context)
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

        form.fields['phone_number'].required = True
        return form

    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def post(self, request, *args, **kwargs):
        if self.new_commcare_user_form.is_valid() and self.custom_data.is_valid():
            username = self.new_commcare_user_form.cleaned_data['username']
            password = self.new_commcare_user_form.cleaned_data['password']
            phone_number = self.new_commcare_user_form.cleaned_data['phone_number']

            if 'location_id' in request.GET:
                loc = get_document_or_404(Location, self.domain,
                                          request.GET.get('location_id'))

            user = CommCareUser.create(
                self.domain,
                username,
                password,
                phone_number=phone_number,
                device_id="Generated from HQ",
                user_data=self.custom_data.get_data_to_save(),
            )

            if 'location_id' in request.GET:
                user.set_location(loc)

            if phone_number:
                initiate_sms_verification_workflow(user, phone_number)

            user_json = {'user_id': user._id, 'text': user.username_in_report}
            return self.render_json_response({"status": "success",
                                              "user": user_json})
        return self.render_form("failure")


class UploadCommCareUsers(BaseManageCommCareUserView):
    template_name = 'users/upload_commcare_users.html'
    urlname = 'upload_commcare_users'
    page_title = ugettext_noop("Bulk Upload Mobile Workers")

    @use_bootstrap3
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
        upload = request.FILES.get('bulk_upload_file')
        try:
            self.workbook = WorkbookJSONReader(upload)
        except (InvalidFileException, BadZipfile):
            try:
                csv.DictReader(io.StringIO(upload.read().decode('ascii'),
                                           newline=None))
                return HttpResponseBadRequest(
                    "CommCare HQ no longer supports CSV upload. "
                    "Please convert to Excel 2007 or higher (.xlsx) "
                    "and try again."
                )
            except UnicodeDecodeError:
                return HttpResponseBadRequest("Unrecognized format")
        except JSONReaderError as e:
            messages.error(request,
                           'Your upload was unsuccessful. %s' % e.message)
            return self.get(request, *args, **kwargs)
        except HeaderValueError as e:
            return HttpResponseBadRequest("Upload encountered a data type error: %s"
                                          % e.message)

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

        self.location_specs = []
        if Domain.get_by_name(self.domain).commtrack_enabled:
            try:
                self.location_specs = self.workbook.get_worksheet(title='locations')
            except WorksheetNotFound:
                # if there is no sheet for locations (since this was added
                # later and is optional) we don't error
                pass

        try:
            check_headers(self.user_specs)
        except UserUploadError as e:
            messages.error(request, _(e.message))
            return HttpResponseRedirect(reverse(UploadCommCareUsers.urlname, args=[self.domain]))

        task_ref = expose_cached_download(payload=None, expiry=1*60*60, file_extension=None)
        task = bulk_upload_async.delay(
            self.domain,
            list(self.user_specs),
            list(self.group_specs),
            list(self.location_specs)
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

    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(UserUploadStatusView, self).dispatch(request, *args, **kwargs)

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
        return render(request, 'style/soil_status_full.html', context)

    def page_url(self):
        return reverse(self.urlname, args=self.args, kwargs=self.kwargs)


@require_can_edit_commcare_users
def user_upload_job_poll(request, domain, download_id, template="users/mobile/partials/user_upload_status.html"):
    try:
        context = get_download_context(download_id, check_state=True)
    except TaskFailedError:
        return HttpResponseServerError()

    context.update({
        'on_complete_short': _('Bulk upload complete.'),
        'on_complete_long': _('Mobile Worker upload has finished'),

    })

    class _BulkUploadResponseWrapper(object):

        def __init__(self, context):
            results = context.get('result', defaultdict(lambda: []))
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
                    errors.append(u'{username}: {flag}'.format(**row))
            errors.extend(self.response_errors)
            return errors

    context['result'] = _BulkUploadResponseWrapper(context)
    return render(request, template, context)


@require_can_edit_commcare_users
def download_commcare_users(request, domain):
    response = HttpResponse(content_type=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename="%s_users.xlsx"' % domain

    try:
        dump_users_and_groups(response, domain)
    except GroupNameError as e:
        group_urls = [
            reverse('group_members', args=[domain, group.get_id])
            for group in e.blank_groups
        ]

        def make_link(url, i):
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                _('Blank Group %s') % i
            )

        group_links = [
            make_link(url, i + 1)
            for i, url in enumerate(group_urls)
        ]
        msg = format_html(
            _(
                'The following groups have no name. '
                'Please name them before continuing: {}'
            ),
            mark_safe(', '.join(group_links))
        )
        messages.error(request, msg, extra_tags='html')
        return HttpResponseRedirect(
            reverse('upload_commcare_users', args=[domain])
        )

    return response


class CommCareUserSelfRegistrationView(TemplateView, DomainViewMixin):
    template_name = "users/mobile/commcare_user_self_register.html"
    urlname = "commcare_user_self_register"
    strict_domain_fetching = True

    @use_bootstrap3
    def dispatch(self, request, *args, **kwargs):
        return super(CommCareUserSelfRegistrationView, self).dispatch(request, *args, **kwargs)

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
            return SelfRegistrationForm(self.request.POST, domain=self.domain)
        else:
            return SelfRegistrationForm(domain=self.domain)

    def get_context_data(self, **kwargs):
        context = super(CommCareUserSelfRegistrationView, self).get_context_data(**kwargs)
        context.update({
            'form': self.form,
            'invitation': self.invitation,
            'can_add_extra_mobile_workers': can_add_extra_mobile_workers(self.request),
            'google_play_store_url': 'https://play.google.com/store/apps/details?id=org.commcare.dalvik&hl=en',
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
            user = CommCareUser.create(
                self.domain,
                self.form.cleaned_data.get('username'),
                self.form.cleaned_data.get('password'),
                phone_number=self.invitation.phone_number,
                device_id='Generated from HQ',
            )
            # Since the user is being created by following the link and token
            # we sent to their phone by SMS, we can verify their phone number
            user.save_verified_number(self.domain, self.invitation.phone_number, True)

            self.invitation.registered_date = datetime.utcnow()
            self.invitation.save()
        return self.get(request, *args, **kwargs)
