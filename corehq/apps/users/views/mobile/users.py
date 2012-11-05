import json
import csv
import io
import uuid
import logging
from django.template.context import RequestContext
from django.template.loader import render_to_string
from openpyxl.shared.exc import InvalidFileException

from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.views.generic.base import TemplateView

from corehq.apps.users.forms import CommCareAccountForm
from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.users.bulkupload import create_or_update_users_and_groups, check_headers
from corehq.apps.users.tasks import bulk_upload_async
from corehq.apps.users.views import _users_context, require_can_edit_web_users, require_can_edit_commcare_users

from dimagi.utils.web import render_to_response, get_url_base
from dimagi.utils.decorators.view import get_file
from dimagi.utils.excel import Excel2007DictReader, WorkbookJSONReader

@require_can_edit_commcare_users
def base_view(request, domain, template="users/commcare_users.html"):
    page = request.GET.get('page', 0)
    limit = request.GET.get('limit', 10)
    total = CommCareUser.total_by_domain(domain)
    cannot_share = json.loads(request.GET.get('cannot_share', 'false'))
    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))
    context = _users_context(request, domain)
    context.update(
        users_list=dict(
            page=page,
            limit=limit,
            total=total,
        ),
        cannot_share=cannot_share,
        show_inactive=show_inactive
    )
    return render_to_response(request, template, context)

@require_can_edit_commcare_users
def user_list(request, domain, template="users/commcare_mobile/commcare_users_list.html"):
    sort_by = request.GET.get('sortBy', 'abc')
    show_more_columns = request.GET.get('show_more_columns') is not None

    cannot_share = json.loads(request.GET.get('cannot_share', 'false'))
    show_inactive = json.loads(request.GET.get('show_inactive', 'false'))

    context = _users_context(request, domain)
    if cannot_share:
        users = CommCareUser.cannot_share(domain)
    else:
        users = CommCareUser.by_domain(domain)
        if show_inactive:
            users.extend(CommCareUser.by_domain(domain, is_active=False))

    if sort_by == 'forms':
        users.sort(key=lambda user: -user.form_count)

    context.update({
        'commcare_users': users,
        'groups': Group.get_case_sharing_groups(domain),
        'show_case_sharing': request.project.case_sharing_included(),
        'show_inactive': show_inactive,
        'cannot_share': cannot_share,
        'show_more_columns': show_more_columns or cannot_share,
        })
    user_list_html = render_to_string(template, context, context_instance=RequestContext(request))
    return HttpResponse(json.dumps(dict(
        user_list_html=user_list_html
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
    return HttpResponseRedirect(reverse('commcare_users', args=[domain]))

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
        except KeyError:
            try:
                self.user_specs = self.workbook.get_worksheet()
            except IndexError:
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
        response_writer = csv.DictWriter(response, ['username', 'flag', 'row'])
        response_rows = []
        async = request.REQUEST.get("async", False)
        if async:
            download_id = uuid.uuid4().hex
            bulk_upload_async.delay(download_id, self.domain,
                list(self.user_specs),
                list(self.group_specs))
            messages.success(request,
                'Your upload is in progress. You can check the progress at "%s%s".' %\
                (get_url_base(), reverse('retrieve_download', kwargs={'download_id': download_id})),
                extra_tags="html")
        else:
            ret = create_or_update_users_and_groups(self.domain, self.user_specs, self.group_specs)
            for error in ret["errors"]:
                messages.error(request, error)

            for row in ret["rows"]:
                response_writer.writerow(row)
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

def upload_commcare_users_example(request, domain):
    response = HttpResponse()
    response['Content-Type'] = 'text/csv'
    response['Content-Disposition'] = 'attachment; filename=users.csv'
    writer = csv.writer(response)
    writer.writerow(['username', 'password', 'phone-number'])
    return response