import copy
import json
import csv
import io
import uuid

from couchdbkit import ResourceNotFound

from django.contrib.auth.forms import SetPasswordForm
from django.utils.safestring import mark_safe

from openpyxl.shared.exc import InvalidFileException
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseBadRequest, Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from django.views.decorators.http import require_POST
from django.contrib import messages

from couchexport.models import Format
from corehq.apps.users.forms import CommCareAccountForm, UpdateCommCareUserInfoForm, CommtrackUserForm, MultipleSelectionForm
from corehq.apps.users.models import CommCareUser, UserRole, CouchUser
from corehq.apps.groups.models import Group
from corehq.apps.users.bulkupload import create_or_update_users_and_groups,\
    check_headers, dump_users_and_groups, GroupNameError, UserUploadError
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseFullEditUserView, BaseUserSettingsView
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.html import format_html
from dimagi.utils.decorators.view import get_file
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound, JSONReaderError


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
    def editable_user(self):
        try:
            user = CommCareUser.get_by_user_id(self.editable_user_id, self.domain)
            if user.is_deleted():
                self.template_name = "users/deleted_account.html"
            return user
        except (ResourceNotFound, CouchUser.AccountTypeError):
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
    def commtrack_user_roles(self):
        # Copied this over from the original view. mwhite, is this the best place for this?
        data_roles = dict((u['slug'], u) for u in [
            {
                'slug': 'commtrack_requester',
                'name': _("CommTrack Requester"),
                'description': _("Responsible for creating requisitions."),
            },
            {
                'slug': 'commtrack_approver',
                'name': _("CommTrack Approver"),
                'description': _(
                    "Responsible for approving requisitions, including "
                    "updating or modifying quantities as needed. Will receive "
                    "a notification when new requisitions are created."),
            },
            {
                'slug': 'commtrack_supplier',
                'name': _("CommTrack Supplier"),
                'description': _(
                    "Responsible for packing orders.  Will receive a "
                    "notification when the approver indicates that "
                    "requisitions are approved, so that he or she can start "
                    "packing it."),
            },
            {
                'slug': 'commtrack_receiver',
                'name': _("CommTrack Receiver"),
                'description': _(
                    "Responsible for receiving orders.  Will receive a "
                    "notification when the supplier indicates that requisitions "
                    "are packed and are ready for pickup, so that he or she can "
                    "come pick it up or better anticipate the delivery."),
            }
        ])

        for k, v in self.custom_user_data.items():
            if k in data_roles:
                data_roles[k]['selected'] = (self.custom_user_data[k] == 'true')
                del self.custom_user_data[k]
        return data_roles

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
    def custom_user_data(self):
        return copy.copy(dict(self.editable_user.user_data))

    @property
    @memoized
    def update_commtrack_form(self):
        if self.request.method == "POST" and self.request.POST['form_type'] == "commtrack":
            return CommtrackUserForm(self.request.POST, domain=self.domain)
        linked_loc = self.editable_user.dynamic_properties().get('commtrack_location')
        return CommtrackUserForm(domain=self.domain, initial={'supply_point': linked_loc})

    @property
    def page_context(self):
        context = {
            'are_groups': bool(len(self.all_groups)),
            'groups_url': reverse('all_groups', args=[self.domain]),
            'group_form': self.group_form,
            'custom_user_data': self.custom_user_data,
            'reset_password_form': self.reset_password_form,
            'is_currently_logged_in_user': self.is_currently_logged_in_user,
        }
        if self.request.project.commtrack_enabled:
            context.update({
                'commtrack': {
                    'roles': self.commtrack_user_roles,
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
                messages.success(request, _("CommTrack information updated!"))
        return super(EditCommCareUserView, self).post(request, *args, **kwargs)


class ListCommCareUsersView(BaseUserSettingsView):
    template_name = "users/mobile/users_list.html"
    urlname = 'commcare_users'
    page_title = ugettext_noop("Mobile Workers")

    DEFAULT_LIMIT = 10

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(ListCommCareUsersView, self).dispatch(request, *args, **kwargs)

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
    def show_case_sharing(self):
        return self.request.project.case_sharing_included()

    @property
    def page_context(self):
        return {
            'users_list': {
                'page': self.users_list_page,
                'limit': self.users_list_limit,
                'total': self.users_list_total,
            },
            'cannot_share': self.cannot_share,
            'show_inactive': self.show_inactive,
            'more_columns': self.more_columns,
            'show_case_sharing': self.show_case_sharing,
            'pagination_limit_options': range(self.DEFAULT_LIMIT, 51, self.DEFAULT_LIMIT),
        }


class AsyncListCommCareUsersView(ListCommCareUsersView):
    urlname = 'user_list'

    @property
    def sort_by(self):
        return self.request.GET.get('sortBy', 'abc')

    @property
    def users_list_skip(self):
        return (self.users_list_page - 1) * self.users_list_limit

    @property
    @memoized
    def users(self):
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

    def get_archive_text(self, is_active):
        if is_active:
            return _("As a result of archiving, this user will no longer appear in reports. "
                     "This action is reversable; you can reactivate this user by viewing "
                     "Show Archived Mobile Workers and clicking 'Unarchive'.")
        return _("This will re-activate the user, and the user will show up in reports again.")

    @property
    def users_list(self):
        users_list = []
        for user in self.users:
            u_data = {
                'user_id': user.user_id,
                'status': "" if user.is_active else _("Archived"),
                'edit_url': reverse(EditCommCareUserView.urlname, args=[self.domain, user.user_id]),
                'username': user.raw_username,
                'full_name': user.full_name,
                'joined_on': user.date_joined.strftime("%d %b %Y"),
                'phone_numbers': user.phone_numbers,
                'form_count': '--',
                'case_count': '--',
                'case_sharing_groups': [],
                'archive_action_text': _("Archive") if user.is_active else _("Un-Archive"),
                'archive_action_desc': self.get_archive_text(user.is_active),
                'archive_action_url': reverse('%s_commcare_user' % ('archive' if user.is_active else 'unarchive'),
                    args=[self.domain, user.user_id]),
                'archive_action_complete': False,
            }
            if self.more_columns:
                u_data.update({
                    'form_count': user.form_count,
                    'case_count': user.case_count,
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
            'users_list': self.users_list,
        }))


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
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.is_active = is_active
    user.save()
    return HttpResponse(json.dumps(dict(
        success=True,
        message=_("User '{user}' has successfully been {action}.").format(
            user=user.raw_username,
            action=_("Un-Archived") if user.is_active else _("Archived"),
        )
    )))

@require_can_edit_commcare_users
@require_POST
def delete_commcare_user(request, domain, user_id):
    user = CommCareUser.get_by_user_id(user_id, domain)
    user.retire()
    messages.success(request, "User %s and all their submissions have been permanently deleted" % user.username)
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
    updated_data = json.loads(request.POST["user-data"])
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
    def password_format(self):
        return self.request.project.password_format()

    @property
    @memoized
    def new_commcare_user_form(self):
        if self.request.method == "POST":
            form = CommCareAccountForm(self.request.POST)
            form.password_format = self.password_format
            return form
        return CommCareAccountForm()

    @property
    def page_context(self):
        return {
            'form': self.new_commcare_user_form,
            'only_numeric': self.password_format == 'n',
        }

    def post(self, request, *args, **kwargs):
        if self.new_commcare_user_form.is_valid():
            username = self.new_commcare_user_form.cleaned_data['username']
            password = self.new_commcare_user_form.cleaned_data['password']
            phone_number = self.new_commcare_user_form.cleaned_data['phone_number']

            couch_user = CommCareUser.create(
                self.domain,
                username,
                password,
                phone_number=phone_number,
                device_id="Generated from HQ"
            )
            return HttpResponseRedirect(reverse(EditCommCareUserView.urlname,
                                                args=[self.domain, couch_user.userID]))
        return self.get(request, *args, **kwargs)


class UploadCommCareUsers(BaseManageCommCareUserView):
    template_name = 'users/upload_commcare_users.html'
    urlname = 'upload_commcare_users'
    page_title = ugettext_noop("Bulk Upload Mobile Workers")

    @property
    def page_context(self):
        return {
            'show_secret_settings': self.request.REQUEST.get("secret", False),
        }

    @method_decorator(get_file)
    def post(self, request, *args, **kwargs):
        """View's dispatch method automatically calls this"""
        redirect = request.POST.get('redirect')

        try:
            self.workbook = WorkbookJSONReader(request.file)
        except InvalidFileException:
            try:
                csv.DictReader(io.StringIO(request.file.read().decode('ascii'),
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
            return HttpResponseRedirect(redirect)

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
            return HttpResponseBadRequest(e)

        response = HttpResponse()
        response_rows = []
        async = request.REQUEST.get("async", False)
        if async:
            download_id = uuid.uuid4().hex
            bulk_upload_async.delay(download_id, self.domain,
                list(self.user_specs),
                list(self.group_specs))
            messages.success(request,
                'Your upload is in progress. You can check the progress <a href="%s">here</a>.' %\
                reverse('hq_soil_download', kwargs={'domain': self.domain, 'download_id': download_id}),
                extra_tags="html")
        else:
            ret = create_or_update_users_and_groups(self.domain, self.user_specs, self.group_specs)
            for error in ret["errors"]:
                messages.error(request, error)

            for row in ret["rows"]:
                response_rows.append(row)

        if redirect:
            if not async:
                messages.success(request,
                                 _('Your bulk user upload is complete!'))
            problem_rows = []
            for row in response_rows:
                if row['flag'] not in ('updated', 'created'):
                    problem_rows.append(row)
            if problem_rows:
                messages.error(
                    request,
                    _('However, we ran into problems with the following users:')
                )
                for row in problem_rows:
                    if row['flag'] == 'missing-data':
                        messages.error(request,
                                       _('A row with no username was skipped'))
                    else:
                        messages.error(request,
                                       '{username}: {flag}'.format(**row))
            return HttpResponseRedirect(redirect)
        else:
            return response


@require_can_edit_commcare_users
def download_commcare_users(request, domain):
    response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename=%s_users.xlsx' % domain

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
