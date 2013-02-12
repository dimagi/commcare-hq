import json
import csv
import io
import uuid
from django.utils.safestring import mark_safe

from openpyxl.shared.exc import InvalidFileException
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.views.generic.base import TemplateView

from couchexport.models import Format
from corehq.apps.users.forms import CommCareAccountForm
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.users.bulkupload import create_or_update_users_and_groups,\
    check_headers, dump_users_and_groups, GroupNameError
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.views import _users_context, require_can_edit_web_users,\
    require_can_edit_commcare_users
from dimagi.utils.html import format_html
from dimagi.utils.web import render_to_response
from dimagi.utils.decorators.view import get_file
from dimagi.utils.excel import WorkbookJSONReader, WorksheetNotFound


DEFAULT_USER_LIST_LIMIT = 10

@require_can_edit_commcare_users
def base_view(request, domain, template="users/mobile/users_list.html"):
    page = request.GET.get('page', 1)
    limit = request.GET.get('limit', DEFAULT_USER_LIST_LIMIT)

    more_columns = json.loads(request.GET.get('more_columns', 'false'))
    cannot_share = json.loads(request.GET.get('cannot_share', 'false'))
    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))

    total = CommCareUser.total_by_domain(domain, is_active=not show_inactive)

    context = _users_context(request, domain)
    context.update(
        users_list=dict(
            page=page,
            limit=limit,
            total=total,
        ),
        cannot_share=cannot_share,
        show_inactive=show_inactive,
        more_columns=more_columns,
        show_case_sharing=request.project.case_sharing_included(),
        pagination_limit_options=range(DEFAULT_USER_LIST_LIMIT, 51, DEFAULT_USER_LIST_LIMIT)
    )
    return render_to_response(request, template, context)

@require_can_edit_commcare_users
def user_list(request, domain):
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', DEFAULT_USER_LIST_LIMIT))
    skip = (page-1)*limit

    sort_by = request.GET.get('sortBy', 'abc')

    more_columns = json.loads(request.GET.get('more_columns', 'false'))
    cannot_share = json.loads(request.GET.get('cannot_share', 'false'))
    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))

    if cannot_share:
        users = CommCareUser.cannot_share(domain, limit=limit, skip=skip)
    else:
        users = CommCareUser.by_domain(domain, is_active=not show_inactive, limit=limit, skip=skip)

    if sort_by == 'forms':
        users.sort(key=lambda user: -user.form_count)

    users_list = []
    for user in users:
        user_data = dict(
            user_id=user.user_id,
            status="" if user.is_active else "Archived",
            edit_url=reverse('user_account', args=[domain, user.user_id]),
            username=user.raw_username,
            full_name=user.full_name,
            joined_on=user.date_joined.strftime("%d %b %Y"),
            phone_numbers=user.phone_numbers,
            form_count="--",
            case_count="--",
            case_sharing_groups=[],
        )
        if more_columns:
            user_data.update(
                form_count=user.form_count,
                case_count=user.case_count,
            )
            if request.project.case_sharing_included():
                user_data.update(
                    case_sharing_groups=[g.name for g in user.get_case_sharing_groups()]
                )
        if request.couch_user.can_edit_commcare_user:
            if user.is_active:
                archive_action_desc = "As a result of archiving, this user will no longer " \
                                      "appear in reports. This action is reversable; you can " \
                                      "reactivate this user by viewing Show Archived Mobile Workers and " \
                                      "clicking 'Unarchive'."
            else:
                archive_action_desc = "This will re-activate the user, and the user will show up in reports again."
            user_data.update(
                archive_action_text="Archive" if user.is_active else "Un-Archive",
                archive_action_url=reverse('%s_commcare_user' % ('archive' if user.is_active else 'unarchive'),
                    args=[domain, user.user_id]),
                archive_action_desc=archive_action_desc,
                archive_action_complete=False,
            )
        users_list.append(user_data)

    return HttpResponse(json.dumps(dict(
        success=True,
        current_page=page,
        users_list=users_list,
    )))

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
        message="User '%s' has successfully been %s." %
                (user.raw_username, "Un-Archived" if user.is_active else "Archived")
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
    return HttpResponseRedirect(reverse('user_account', args=[domain, user_id]))

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
    return HttpResponseRedirect(reverse('user_account', args=[domain, couch_user_id]))

@require_can_edit_web_users
def add_commcare_account(request, domain, template="users/add_commcare_account.html"):
    """
    Create a new commcare account
    """
    context = _users_context(request, domain)
    if request.method == "POST":
        form = CommCareAccountForm(request.POST)
        form.password_format = request.project.password_format()
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            couch_user = CommCareUser.create(domain, username, password, device_id='Generated from HQ')
            couch_user.save()
            return HttpResponseRedirect(reverse("user_account", args=[domain, couch_user.userID]))
    else:
        form = CommCareAccountForm()
    context.update(form=form)
    context.update(only_numeric=(request.project.password_format() == 'n'))
    return render_to_response(request, template, context)


class UploadCommCareUsers(TemplateView):

    template_name = 'users/upload_commcare_users.html'

    def get_context_data(self, **kwargs):
        """TemplateView automatically calls this to render the view (on a get)"""
        context = _users_context(self.request, self.domain)
        context["show_secret_settings"] = self.request.REQUEST.get("secret", False)
        return context

    @method_decorator(get_file)
    def post(self, request):
        """View's dispatch method automatically calls this"""

        try:
            self.workbook = WorkbookJSONReader(request.file)
        except InvalidFileException:
            try:
                csv.DictReader(io.StringIO(request.file.read().decode('ascii'), newline=None))
                return HttpResponseBadRequest(
                    "CommCare HQ no longer supports CSV upload. "
                    "Please convert to Excel 2007 or higher (.xlsx) and try again."
                )
            except UnicodeDecodeError:
                return HttpResponseBadRequest("Unrecognized format")

        try:
            self.user_specs = self.workbook.get_worksheet(title='users')
        except WorksheetNotFound:
            try:
                self.user_specs = self.workbook.get_worksheet()
            except WorksheetNotFound:
                return HttpResponseBadRequest("Workbook has no worksheets")

        try:
            self.group_specs = self.workbook.get_worksheet(title='groups')
        except KeyError:
            self.group_specs = []

        try:
            check_headers(self.user_specs)
        except Exception, e:
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

        redirect = request.POST.get('redirect')
        if redirect:
            if not async:
                messages.success(request, 'Your bulk user upload is complete!')
            problem_rows = []
            for row in response_rows:
                if row['flag'] not in ('updated', 'created'):
                    problem_rows.append(row)
            if problem_rows:
                messages.error(request, 'However, we ran into problems with the following users:')
                for row in problem_rows:
                    if row['flag'] == 'missing-data':
                        messages.error(request, 'A row with no username was skipped')
                    else:
                        messages.error(request, '{username}: {flag}'.format(**row))
            return HttpResponseRedirect(redirect)
        else:
            return response


    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, domain, *args, **kwargs):
        self.domain = domain
        return super(UploadCommCareUsers, self).dispatch(request, *args, **kwargs)

@require_can_edit_commcare_users
def download_commcare_users(request, domain):
    response = HttpResponse(mimetype=Format.from_format('xlsx').mimetype)
    response['Content-Disposition'] = 'attachment; filename=%s_users.xlsx' % domain

    try:
        dump_users_and_groups(response, domain)
    except GroupNameError as e:
        group_urls = [reverse('group_members', args=[domain, group.get_id])
                      for group in e.blank_groups]

        def make_link(url, i):
            return format_html('<a href="{}">{}</a>',
                               url, _('Blank Group %s') % i)
        enumerate(group_urls)
        group_links = [make_link(url, i + 1)
                       for i, url in enumerate(group_urls)]
        msg = format_html(_('The following groups have no name. '
                            'Please name them before continuing: {}'),
            mark_safe(', '.join(group_links))
        )
        print msg
        messages.error(request,
            msg,
            extra_tags='html',
        )
        return HttpResponseRedirect(
            reverse('upload_commcare_users', args=[domain]))

    return response
