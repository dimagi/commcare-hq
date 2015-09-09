from collections import defaultdict
import json
import csv
import io

from couchdbkit import ResourceNotFound

from django.contrib.auth.forms import SetPasswordForm
from django.http.response import HttpResponseServerError
from django.shortcuts import render
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from braces.views import JsonRequestResponseMixin
from openpyxl.utils.exceptions import InvalidFileException
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST
from django.views.generic import View
from django.contrib import messages
from corehq import privileges
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    EntryPoint,
)
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.es.queries import search_string_query
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.locations.models import Location
from corehq.apps.users.util import can_add_extra_mobile_workers
from corehq.apps.custom_data_fields import CustomDataEditor
from corehq.const import USER_DATE_FORMAT
from corehq.elastic import es_query, ES_URLS, ADD_TO_ES_FILTER
from corehq.util.couch import get_document_or_404
from corehq.util.spreadsheets.excel import JSONReaderError, HeaderValueError, \
    WorksheetNotFound, WorkbookJSONReader

from couchexport.models import Format
from corehq.apps.users.forms import (CommCareAccountForm, UpdateCommCareUserInfoForm, CommtrackUserForm,
                                     MultipleSelectionForm, ConfirmExtraUserChargesForm)
from corehq.apps.users.models import CommCareUser, UserRole, CouchUser
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.locations.permissions import user_can_edit_any_location
from corehq.apps.users.bulkupload import check_headers, dump_users_and_groups, GroupNameError, UserUploadError
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseFullEditUserView, BaseUserSettingsView
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import has_privilege
from soil.exceptions import TaskFailedError
from soil.util import get_download_context, expose_cached_download
from .custom_data_fields import UserFieldsView

BULK_MOBILE_HELP_SITE = ("https://confluence.dimagi.com/display/commcarepublic"
                         "/Create+and+Manage+CommCare+Mobile+Workers#Createand"
                         "ManageCommCareMobileWorkers-B.UseBulkUploadtocreatem"
                         "ultipleusersatonce")
DEFAULT_USER_LIST_LIMIT = 10


class EditCommCareUserView(BaseFullEditUserView):
    template_name = "users/edit_commcare_user.html"
    urlname = "edit_commcare_user"
    user_update_form_class = UpdateCommCareUserInfoForm
    page_title = ugettext_noop("Edit Mobile Worker")

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(EditCommCareUserView, self).dispatch(request, *args, **kwargs)

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
            if not user:
                raise Http404()
            if user.is_deleted():
                self.template_name = "users/deleted_account.html"
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
        return SetPasswordForm(user="")

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
        return CommtrackUserForm(domain=self.domain, initial={'location': initial_id})

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
        if self.can_change_user_roles:
            form.load_roles(current_role=self.existing_role, role_choices=self.user_role_choices)
        else:
            del form.fields['role']
        return form

    @property
    def parent_pages(self):
        return [{
            'title': _("Mobile Workers"),
            'url': reverse(ListCommCareUsersView.urlname, args=[self.domain]),
        }]

    def post(self, request, *args, **kwargs):
        if request.POST['form_type'] == "commtrack":
            if self.update_commtrack_form.is_valid():
                self.update_commtrack_form.save(self.editable_user)
                messages.success(request, _("CommCare Supply information updated!"))
        return super(EditCommCareUserView, self).post(request, *args, **kwargs)

    def custom_user_is_valid(self):
        if self.custom_data.is_valid():
            self.editable_user.user_data = self.custom_data.get_data_to_save()
            self.editable_user.save()
            return True
        else:
            return False


class ListCommCareUsersView(BaseUserSettingsView):
    template_name = "users/mobile/users_list.html"
    urlname = 'commcare_users'
    page_title = ugettext_noop("Mobile Workers")

    DEFAULT_LIMIT = 10

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(ListCommCareUsersView, self).dispatch(request, *args, **kwargs)

    @property
    def can_bulk_edit_users(self):
        if not user_can_edit_any_location(self.request.couch_user, self.request.project):
            return False
        return has_privilege(self.request, privileges.BULK_USER_MANAGEMENT)

    @property
    def can_add_extra_users(self):
        return can_add_extra_mobile_workers(self.request)

    @property
    def can_edit_user_archive(self):
        return self.couch_user.can_edit_commcare_users and (
            (self.show_inactive and self.can_add_extra_users) or not self.show_inactive)

    @property
    def can_edit_billing_info(self):
        return self.couch_user.is_domain_admin(self.domain) or self.couch_user.is_superuser

    def _escape_val_error(self, expression, default):
        try:
            return expression()
        except ValueError:
            return default

    @property
    def users_list_page(self):
        return self._escape_val_error(
            lambda: int(self.request.GET.get('page', 1)),
            1
        )

    @property
    def users_list_limit(self):
        return self._escape_val_error(
            lambda: int(self.request.GET.get('limit', self.DEFAULT_LIMIT)),
            self.DEFAULT_LIMIT
        )

    @property
    @memoized
    def users_list_total(self):
        if self.query:
            return self.total_users_from_es
        return CommCareUser.total_by_domain(self.domain, is_active=not self.show_inactive)

    @property
    @memoized
    def more_columns(self):
        return self._escape_val_error(
            lambda: json.loads(self.request.GET.get('more_columns', 'false')),
            False
        )

    @property
    @memoized
    def cannot_share(self):
        return self._escape_val_error(
            lambda: json.loads(self.request.GET.get('cannot_share', 'false')),
            False
        )

    @property
    @memoized
    def show_inactive(self):
        return self._escape_val_error(
            lambda: json.loads(self.request.GET.get('show_inactive', 'false')),
            False
        )

    @property
    @memoized
    def query(self):
        return self.request.GET.get('query')

    @property
    def show_case_sharing(self):
        return self.request.project.case_sharing_included()

    def get_groups(self):
        return Group.by_domain(self.domain)

    @property
    def page_context(self):
        return {
            'data_list': {
                'page': self.users_list_page,
                'limit': self.users_list_limit,
                'total': self.users_list_total,
            },
            'groups': self.get_groups(),
            'cannot_share': self.cannot_share,
            'show_inactive': self.show_inactive,
            'more_columns': self.more_columns,
            'show_case_sharing': self.show_case_sharing,
            'pagination_limit_options': (10, 20, 50, 100),
            'query': self.query,
            'can_bulk_edit_users': self.can_bulk_edit_users,
            'can_add_extra_users': self.can_add_extra_users,
            'can_edit_user_archive': self.can_edit_user_archive,
            'can_edit_billing_info': self.can_edit_billing_info,
        }




class AsyncListCommCareUsersView(ListCommCareUsersView):
    urlname = 'user_list'
    es_results = None

    @property
    def sort_by(self):
        return self.request.GET.get('sortBy', 'abc')

    @property
    def users_list_skip(self):
        return (self.users_list_page - 1) * self.users_list_limit

    @property
    @memoized
    def users(self):
        if self.query:
            return self.users_from_es

        if self.cannot_share:
            users = CommCareUser.cannot_share(
                self.domain,
                limit=self.users_list_limit,
                skip=self.users_list_skip
            )
        else:
            users = CommCareUser.by_domain(
                self.domain,
                is_active=not self.show_inactive,
                limit=self.users_list_limit,
                skip=self.users_list_skip
            )
        if self.sort_by == 'forms':
            users.sort(key=lambda user: -user.form_count)
        return users

    def query_es(self):
        q = {
            "filter": {"and": ADD_TO_ES_FILTER["users"][:]},
            "sort": {'username.exact': 'asc'},
        }
        default_fields = ["username.exact", "last_name", "first_name"]
        q["query"] = search_string_query(self.query, default_fields)
        params = {
            "domain": self.domain,
            "is_active": not self.show_inactive,
        }
        self.es_results = es_query(params=params, q=q, es_url=ES_URLS["users"],
                           size=self.users_list_limit, start_at=self.users_list_skip)

    @property
    @memoized
    def users_from_es(self):
        if self.es_results is None:
            self.query_es()
        users = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]
        return [CommCareUser.wrap(user) for user in users]

    @property
    @memoized
    def total_users_from_es(self):
        if self.es_results is None:
            self.query_es()
        return self.es_results.get("hits", {}).get("total", 0)

    def get_archive_text(self, is_active):
        if is_active:
            return _("As a result of deactivating, this user will no longer appear in reports. "
                     "This action is reversable; you can reactivate this user by viewing "
                     "'Show Deactivated Mobile Workers' and clicking 'Reactivate'.")
        return _("This will reactivate the user, and the user will show up in reports again.")

    @property
    def users_list(self):
        users_list = []
        for user in self.users:
            u_data = {
                'user_id': user.user_id,
                'status': "" if user.is_active else _("Deactivated"),
                'edit_url': reverse(EditCommCareUserView.urlname, args=[self.domain, user.user_id]),
                'username': user.raw_username,
                'full_name': user.full_name,
                'joined_on': user.date_joined.strftime(USER_DATE_FORMAT),
                'phone_numbers': user.phone_numbers,
                'form_count': '--',
                'case_count': '--',
                'case_sharing_groups': [],
                'archive_action_text': _("Deactivate") if user.is_active else _("Reactivate"),
                'archive_action_desc': self.get_archive_text(user.is_active),
                'archive_action_url': reverse('%s_commcare_user' % ('archive' if user.is_active else 'unarchive'),
                    args=[self.domain, user.user_id]),
                'archive_action_complete': False,
            }
            if self.more_columns:
                u_data.update({
                    'form_count': user.form_count,
                    'case_count': user.analytics_only_case_count,
                })
                if self.show_case_sharing:
                    u_data.update({
                        'case_sharing_groups': [g.name for g in user.get_case_sharing_groups()],
                    })
            users_list.append(u_data)
        return users_list

    def render_to_response(self, context, **response_kwargs):
        return HttpResponse(json.dumps({
            'success': True,
            'current_page': self.users_list_page,
            'data_list_total': self.users_list_total,
            'data_list': self.users_list,
        }))


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
            return HttpResponseRedirect(reverse(CreateCommCareUserView.urlname, args=[self.domain]))
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
                    ListCommCareUsersView.urlname, args=[self.domain]
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
    return HttpResponseRedirect(reverse('commcare_users', args=[domain]))

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
    return HttpResponseRedirect(reverse('commcare_users', args=[domain]))

@require_can_edit_commcare_users
@require_POST
def restore_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.unretire()
    messages.success(request, "User %s and all their submissions have been restored" % user.username)
    return HttpResponseRedirect(reverse(EditCommCareUserView.urlname, args=[domain, user_id]))

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
            'title': ListCommCareUsersView.page_title,
            'url': reverse(ListCommCareUsersView.urlname, args=[self.domain]),
        }]


class CreateCommCareUserView(BaseManageCommCareUserView):
    template_name = "users/add_commcare_account.html"
    urlname = 'add_commcare_account'
    page_title = ugettext_noop("New Mobile Worker")

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
            return CommCareAccountForm(self.request.POST)
        return CommCareAccountForm()

    @property
    def page_context(self):
        return {
            'form': self.new_commcare_user_form,
            'data_fields_form': self.custom_data.form,
        }

    def dispatch(self, request, *args, **kwargs):
        if not can_add_extra_mobile_workers(request):
            return HttpResponseRedirect(reverse(ListCommCareUsersView.urlname, args=[self.domain]))
        return super(CreateCommCareUserView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.new_commcare_user_form.is_valid() and self.custom_data.is_valid():
            username = self.new_commcare_user_form.cleaned_data['username']
            password = self.new_commcare_user_form.cleaned_data['password']
            phone_number = self.new_commcare_user_form.cleaned_data['phone_number']

            if 'location_id' in request.GET:
                loc = get_document_or_404(Location, self.domain, request.GET.get('location_id'))

            couch_user = CommCareUser.create(
                self.domain,
                username,
                password,
                phone_number=phone_number,
                device_id="Generated from HQ",
                user_data=self.custom_data.get_data_to_save(),
            )

            if 'location_id' in request.GET:
                couch_user.set_location(loc)

            return HttpResponseRedirect(reverse(EditCommCareUserView.urlname,
                                                args=[self.domain, couch_user.userID]))
        return self.get(request, *args, **kwargs)


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
            data['domain'] = self.domain
            return CommCareAccountForm(data)
        return CommCareAccountForm()

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

            user_json = {'user_id': user._id, 'text': user.username_in_report}
            return self.render_json_response({"status": "success",
                                              "user": user_json})
        return self.render_form("failure")


class UploadCommCareUsers(BaseManageCommCareUserView):
    template_name = 'users/upload_commcare_users.html'
    urlname = 'upload_commcare_users'
    page_title = ugettext_noop("Bulk Upload Mobile Workers")

    @method_decorator(requires_privilege_with_fallback(privileges.BULK_USER_MANAGEMENT))
    def dispatch(self, request, *args, **kwargs):
        return super(UploadCommCareUsers, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
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
            'show_secret_settings': self.request.REQUEST.get("secret", False),
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
        except InvalidFileException:
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

        task_ref = expose_cached_download(None, expiry=1*60*60, file_extension=None)
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

    def get(self, request, *args, **kwargs):
        context = super(UserUploadStatusView, self).main_context
        context.update({
            'domain': self.domain,
            'download_id': kwargs['download_id'],
            'poll_url': reverse('user_upload_job_poll', args=[self.domain, kwargs['download_id']]),
            'title': _("Mobile Worker Upload Status"),
            'progress_text': _("Importing your data. This may take some time..."),
            'error_text': _("Problem importing data! Please try again or report an issue."),
            'next_url': reverse(ListCommCareUsersView.urlname, args=[self.domain]),
            'next_url_text': _("Return to manage mobile workers"),
        })
        return render(request, 'style/bootstrap2/soil_status_full.html', context)

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
