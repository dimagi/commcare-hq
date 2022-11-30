import csv
import itertools
import settings
import os
import urllib.parse
import uuid
from collections import Counter
from datetime import datetime, timedelta
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import mail_admins
from django.db.models import Q
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.http.response import Http404
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.generic import FormView, TemplateView, View

from couchdbkit.exceptions import ResourceNotFound
from lxml import etree
from lxml.builder import E
from two_factor.utils import default_device

from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps.hqadmin.utils import unset_password
from couchexport.models import Format
from couchforms.openrosa_response import RESPONSE_XMLNS
from dimagi.utils.django.email import send_HTML_email

from corehq.apps.accounting.utils import is_accounting_admin
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.auth import basicauth
from corehq.apps.domain.decorators import (
    check_lockout,
    domain_admin_required,
    login_or_basic,
    require_superuser,
)
from corehq.apps.hqadmin.forms import (
    DisableTwoFactorForm,
    DisableUserForm,
    SuperuserManagementForm,
    OffboardingUserListForm,
)
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView
from corehq.apps.hqmedia.tasks import create_files_for_ccz
from corehq.apps.ota.views import get_restore_params, get_restore_response
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import CommCareUser, CouchUser, WebUser
from corehq.apps.users.util import format_username, log_user_change
from corehq.const import USER_CHANGE_VIA_WEB
from corehq.util import reverse
from corehq.util.timer import TimingContext


class UserAdministration(BaseAdminSectionView):
    section_name = gettext_lazy("User Administration")


class SuperuserManagement(UserAdministration):
    urlname = 'superuser_management'
    page_title = _("Grant or revoke superuser access")
    template_name = 'hqadmin/superuser_management.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(SuperuserManagement, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        # only users with can_assign_superuser privilege can change superuser and staff status
        can_toggle_status = WebUser.from_django_user(self.request.user).can_assign_superuser
        # render validation errors if rendered after POST
        args = [self.request.POST] if self.request.POST else []
        return {
            'form': SuperuserManagementForm(*args),
            'users': augmented_superusers(include_can_assign_superuser=True),
            'can_toggle_status': can_toggle_status
        }

    def post(self, request, *args, **kwargs):
        can_toggle_status = WebUser.from_django_user(self.request.user).can_assign_superuser
        if not can_toggle_status:
            messages.error(request, _("You do not have permission to update superuser or staff status"))
            return self.get(request, *args, **kwargs)
        form = SuperuserManagementForm(self.request.POST)
        if form.is_valid():
            users = form.cleaned_data['csv_email_list']
            is_superuser = 'is_superuser' in form.cleaned_data['privileges']
            is_staff = 'is_staff' in form.cleaned_data['privileges']
            can_assign_superuser = 'can_assign_superuser' in form.cleaned_data['can_assign_superuser']
            user_changes = []
            for user in users:
                fields_changed = {}
                # save user object only if needed and just once
                if can_toggle_status and user.is_superuser is not is_superuser:
                    user.is_superuser = is_superuser
                    fields_changed['is_superuser'] = is_superuser

                if can_toggle_status and user.is_staff is not is_staff:
                    user.is_staff = is_staff
                    fields_changed['is_staff'] = is_staff

                web_user = WebUser.from_django_user(user)
                if can_toggle_status and web_user.can_assign_superuser is not can_assign_superuser:
                    web_user.can_assign_superuser = can_assign_superuser
                    web_user.save()
                    fields_changed['can_assign_superuser'] = can_assign_superuser

                if fields_changed:
                    user.save()
                    couch_user = CouchUser.from_django_user(user)
                    log_user_change(by_domain=None, for_domain=None, couch_user=couch_user,
                                    changed_by_user=self.request.couch_user,
                                    changed_via=USER_CHANGE_VIA_WEB, fields_changed=fields_changed,
                                    by_domain_required_for_log=False,
                                    for_domain_required_for_log=False)

                    #formatting for user_changes list
                    fields_changed['email'] = user.username
                    if 'is_superuser' not in fields_changed:
                        fields_changed['same_superuser'] = user.is_superuser
                    if 'is_staff' not in fields_changed:
                        fields_changed['same_staff'] = user.is_staff
                    if 'can_assign_superuser' not in fields_changed:
                        fields_changed['same_management_privilege'] = web_user.can_assign_superuser
                    user_changes.append(fields_changed)
            if user_changes:
                send_email_notif(user_changes, self.request.couch_user.username)
            messages.success(request, _("Successfully updated superuser permissions"))

        return self.get(request, *args, **kwargs)


def send_email_notif(user_changes, changed_by_user):
    mail_admins(
        "Superuser privilege / Staff status was changed",
        "",
        html_message=render_to_string('hqadmin/email/superuser_staff_email.html', context={
            'user_changes': user_changes,
            'changed_by_user': changed_by_user,
            'env': settings.SERVER_ENVIRONMENT
        })
    )
    return


@require_superuser
def superuser_table(request):
    superusers = augmented_superusers(include_can_assign_superuser=True)
    f = StringIO()
    csv_writer = csv.writer(f)
    csv_writer.writerow(['Username', 'Developer', 'Superuser', 'Can assign Superuser', 'Two Factor Enabled'])
    for user in superusers:
        csv_writer.writerow([
            user.username, user.is_staff, user.is_superuser, user.can_assign_superuser, user.two_factor_enabled])
    response = HttpResponse(content_type=Format.from_format('csv').mimetype)
    response['Content-Disposition'] = 'attachment; filename="superuser_table.csv"'
    response.write(f.getvalue())
    return response


def augmented_superusers(users=None, include_accounting_admin=False, include_can_assign_superuser=False):
    if not users:
        users = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True)).order_by("username")
    augmented_users = _augment_users_with_two_factor_enabled(users)
    if include_accounting_admin:
        return _augment_users_with_accounting_admin(augmented_users)
    if include_can_assign_superuser:
        return _augment_users_with_can_assign_superuser(augmented_users)
    return augmented_users


def _augment_users_with_can_assign_superuser(users):
    """Annotate a User queryset with a can_assign_superuser field"""
    for user in users:
        web_user = WebUser.from_django_user(user)
        user.can_assign_superuser = web_user.can_assign_superuser
    return users


def _augment_users_with_two_factor_enabled(users):
    """Annotate a User queryset with a two_factor_enabled field"""
    for user in users:
        user.two_factor_enabled = bool(default_device(user))
    return users


def _augment_users_with_accounting_admin(users):
    for user in users:
        user.is_accounting_admin = is_accounting_admin(user)
    return users


class AdminRestoreView(TemplateView):
    template_name = 'hqadmin/admin_restore.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(AdminRestoreView, self).dispatch(request, *args, **kwargs)

    def _validate_user_access(self, user):
        return True

    def get(self, request, *args, **kwargs):
        full_username = request.GET.get('as', '')

        if not full_username or '@' not in full_username:
            msg = 'Please specify a user using ?as=user@domain\nOr a web-user using ?as=email&domain=domain'
            return HttpResponseBadRequest(msg)

        username, possible_domain = full_username.split("@")
        if "." in possible_domain:
            if possible_domain.endswith(settings.HQ_ACCOUNT_ROOT):
                self.domain = possible_domain.split(".")[0]
                self.user = CommCareUser.get_by_username(full_username)
            else:
                self.domain = request.GET.get('domain', '')
                self.user = CouchUser.get_by_username(full_username)
        else:
            self.domain = possible_domain
            full_username = format_username(username, self.domain)
            self.user = CommCareUser.get_by_username(full_username)

        if not self.user:
            return HttpResponseNotFound('User %s not found.' % full_username)

        if self.user.is_web_user() and not self.domain:
            msg = 'Please specify domain for web-user using ?as=email&domain=domain'
            return HttpResponseBadRequest(msg)

        if not self._validate_user_access(self.user):
            return HttpResponseNotFound('User %s not found.' % full_username)

        self.app_id = kwargs.get('app_id', None)

        raw = request.GET.get('raw') == 'true'
        if raw:
            response, _ = self._get_restore_response()
            return response

        download = request.GET.get('download') == 'true'
        if download:
            response, _ = self._get_restore_response()
            response['Content-Disposition'] = "attachment; filename={}-restore.xml".format(username)
            return response

        return super(AdminRestoreView, self).get(request, *args, **kwargs)

    def _get_restore_response(self):
        params = get_restore_params(self.request, self.domain)
        params['as_user'] = self.user.username
        return get_restore_response(
            self.domain, self.request.couch_user, app_id=self.app_id,
            **params
        )

    @staticmethod
    def _parse_reports(xpath, xml_payload):
        reports = xml_payload.findall(xpath)
        report_row_counts = {}
        for report in reports:
            if 'report_id' in report.attrib:
                report_id = report.attrib['report_id']
                if 'id' in report.attrib:
                    report_id = '--'.join([report.attrib['id'], report_id])
                report_row_count = len(report.findall('{{{0}}}rows/{{{0}}}row'.format(RESPONSE_XMLNS)))
                report_row_counts[report_id] = report_row_count
        return len(reports), report_row_counts

    @staticmethod
    def get_stats_from_xml(xml_payload):
        restore_id_element = xml_payload.find('{{{0}}}Sync/{{{0}}}restore_id'.format(SYNC_XMLNS))
        # note: restore_id_element is ALWAYS falsy, so check explicitly for `None`
        restore_id = restore_id_element.text if restore_id_element is not None else None
        cases = xml_payload.findall('{http://commcarehq.org/case/transaction/v2}case')
        num_cases = len(cases)

        create_case_type = [case.find(
            '{http://commcarehq.org/case/transaction/v2}create/'
            '{http://commcarehq.org/case/transaction/v2}case_type'
        ) for case in cases if len(case) and hasattr(case, "type")]
        update_case_type = [case.find(
            '{http://commcarehq.org/case/transaction/v2}update/'
            '{http://commcarehq.org/case/transaction/v2}case_type'
        ) for case in cases if len(case) and hasattr(case, "type")]
        case_type_counts = dict(Counter([
            case.type for case in itertools.chain(create_case_type, update_case_type)
        ]))

        locations = xml_payload.findall(
            "{{{0}}}fixture[@id='locations']/{{{0}}}locations/{{{0}}}location".format(RESPONSE_XMLNS)
        )
        num_locations = len(locations)
        location_type_counts = dict(Counter(location.attrib['type'] for location in locations))

        num_v1_reports, v1_report_row_counts = AdminRestoreView._parse_reports(
            "{{{0}}}fixture[@id='commcare:reports']/{{{0}}}reports/".format(RESPONSE_XMLNS), xml_payload
        )

        num_v2_reports, v2_report_row_counts = AdminRestoreView._parse_reports(
            # the @id is dynamic, so we can't search for it directly - instead, look for the right format
            "{{{0}}}fixture[@report_id][{{{0}}}rows]".format(RESPONSE_XMLNS), xml_payload
        )

        num_ledger_entries = len(xml_payload.findall(
            "{{{0}}}balance/{{{0}}}entry".format(COMMTRACK_REPORT_XMLNS)
        ))
        return {
            'restore_id': restore_id,
            'num_cases': num_cases,
            'num_locations': num_locations,
            'num_v1_reports': num_v1_reports,
            'num_v2_reports': num_v2_reports,
            'case_type_counts': case_type_counts,
            'location_type_counts': location_type_counts,
            'v1_report_row_counts': v1_report_row_counts,
            'v2_report_row_counts': v2_report_row_counts,
            'num_ledger_entries': num_ledger_entries,
        }

    def get_context_data(self, **kwargs):
        context = super(AdminRestoreView, self).get_context_data(**kwargs)
        response, timing_context = self._get_restore_response()
        timing_context = timing_context or TimingContext(self.user.username)
        if isinstance(response, StreamingHttpResponse):
            string_payload = b''.join(response.streaming_content)
            xml_payload = etree.fromstring(string_payload)
            context.update(self.get_stats_from_xml(xml_payload))
        else:
            if response.status_code in (401, 404):
                # corehq.apps.ota.views.get_restore_response couldn't find user or user didn't have perms
                xml_payload = E.error(response.content.decode())
            elif response.status_code == 412:
                # RestoreConfig.get_response returned HttpResponse 412. Response content is already XML
                xml_payload = etree.fromstring(response.content)
            else:
                message = _(
                    'Unexpected restore response {}: {}. '
                    'If you believe this is a bug please report an issue.'
                ).format(response.status_code, response.content.decode('utf-8'))
                xml_payload = E.error(message)
        formatted_payload = etree.tostring(xml_payload, pretty_print=True, encoding='utf-8').decode('utf-8')
        hide_xml = self.request.GET.get('hide_xml') == 'true'
        context.update({
            'payload': formatted_payload,
            'status_code': response.status_code,
            'timing_data': timing_context.to_list(),
            'hide_xml': hide_xml,
        })
        return context


class DomainAdminRestoreView(AdminRestoreView):
    urlname = 'domain_admin_restore'

    def dispatch(self, request, *args, **kwargs):
        return TemplateView.dispatch(self, request, *args, **kwargs)

    @method_decorator(login_or_basic)
    @method_decorator(domain_admin_required)
    def get(self, request, domain, **kwargs):
        self.domain = domain
        return super(DomainAdminRestoreView, self).get(request, **kwargs)

    def _validate_user_access(self, user):
        return user.is_member_of(self.domain)


@require_superuser
def web_user_lookup(request):
    template = "hqadmin/web_user_lookup.html"
    web_user_email = request.GET.get("q", "").lower()

    context = {
        'current_page': {
            'title': "Look up user by email",
            'page_name': "Look up user by email",
        },
        'section': {
            'page_name': UserAdministration.section_name,
            'url': reverse("default_admin_report"),
        },
    }

    if not web_user_email:
        return render(request, template, context)

    web_user = WebUser.get_by_username(web_user_email)
    context.update({
        'audit_report_url': reverse('admin_report_dispatcher', args=('user_audit_report',)),
    })
    if web_user is None:
        messages.error(
            request, "Sorry, no user found with email {}. Did you enter it correctly?".format(web_user_email)
        )
    else:
        from django_otp import user_has_device
        context['web_user'] = web_user
        django_user = web_user.get_django_user()
        context['has_two_factor'] = user_has_device(django_user)
    return render(request, template, context)


@method_decorator(require_superuser, name='dispatch')
class DisableUserView(FormView):
    template_name = 'hqadmin/disable_user.html'
    success_url = None
    form_class = DisableUserForm
    urlname = 'disable_user'

    def get_initial(self):
        return {
            'user': self.user,
            'reset_password': False,
        }

    @property
    def username(self):
        return self.request.GET.get("username")

    @cached_property
    def user(self):
        try:
            return User.objects.get(username__iexact=self.username)
        except User.DoesNotExist:
            return None

    @property
    def redirect_url(self):
        base_url = reverse('web_user_lookup')
        if self.username:
            encoded_username = urllib.parse.quote(self.username) if self.username else None
            return '{}?q={}'.format(base_url, encoded_username)

        return base_url

    def get(self, request, *args, **kwargs):
        if not self.user:
            return self.redirect_response(request)

        return super(DisableUserView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(DisableUserView, self).get_context_data(**kwargs)
        context['verb'] = 'disable' if self.user.is_active else 'enable'
        context['username'] = self.username
        return context

    def redirect_response(self, request):
        messages.warning(request, _('User with username %(username)s not found.') % {
            'username': self.username
        })
        return redirect(self.redirect_url)

    def form_valid(self, form):
        change_messages = {}
        if not self.user:
            return self.redirect_response(self.request)

        reset_password = form.cleaned_data['reset_password']
        if reset_password:
            unset_password(self.user)
            change_messages.update(UserChangeMessage.password_reset())

        # toggle active state
        self.user.is_active = not self.user.is_active
        self.user.save()

        verb = 're-enabled' if self.user.is_active else 'disabled'
        reason = form.cleaned_data['reason']
        change_messages.update(UserChangeMessage.status_update(self.user.is_active, reason))
        couch_user = CouchUser.from_django_user(self.user)
        log_user_change(by_domain=None, for_domain=None, couch_user=couch_user,
                        changed_by_user=self.request.couch_user,
                        changed_via=USER_CHANGE_VIA_WEB, change_messages=change_messages,
                        fields_changed={'is_active': self.user.is_active},
                        by_domain_required_for_log=False,
                        for_domain_required_for_log=False)
        mail_admins(
            "User account {}".format(verb),
            "The following user account has been {verb}: \n"
            "    Account: {username}\n"
            "    Reset by: {reset_by}\n"
            "    Password reset: {password_reset}\n"
            "    Reason: {reason}".format(
                verb=verb,
                username=self.username,
                reset_by=self.request.user.username,
                password_reset=str(reset_password),
                reason=reason,
            )
        )
        send_HTML_email(
            "%sYour account has been %s" % (settings.EMAIL_SUBJECT_PREFIX, verb),
            couch_user.get_email(),
            render_to_string('hqadmin/email/account_disabled_email.html', context={
                'support_email': settings.SUPPORT_EMAIL,
                'password_reset': reset_password,
                'user': self.user,
                'verb': verb,
                'reason': form.cleaned_data['reason'],
            }),
        )

        messages.success(self.request, _('Account successfully %(verb)s.' % {'verb': verb}))
        return redirect(self.redirect_url)


@method_decorator(require_superuser, name='dispatch')
class DisableTwoFactorView(FormView):
    """
    View for disabling two-factor for a user's account.
    """
    template_name = 'hqadmin/disable_two_factor.html'
    success_url = None
    form_class = DisableTwoFactorForm
    urlname = 'disable_two_factor'

    def get_initial(self):
        return {
            'username': self.request.GET.get("q"),
            'disable_for_days': 0,
        }

    def render_to_response(self, context, **response_kwargs):
        context.update({
            'username': self.request.GET.get("q"),
        })
        return super().render_to_response(context, **response_kwargs)

    def get(self, request, *args, **kwargs):
        from django_otp import user_has_device

        username = request.GET.get("q")
        redirect_url = '{}?q={}'.format(reverse('web_user_lookup'), username)
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            messages.warning(request, _('User with username %(username)s not found.') % {
                'username': username
            })
            return redirect(redirect_url)

        if not user_has_device(user):
            messages.warning(request, _(
                'User with username %(username)s does not have Two-Factor Auth enabled.') % {
                'username': username
            })
            return redirect(redirect_url)

        return super(DisableTwoFactorView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        from django_otp import devices_for_user

        username = form.cleaned_data['username']
        user = User.objects.get(username__iexact=username)
        for device in devices_for_user(user):
            device.delete()

        couch_user = CouchUser.from_django_user(user)
        disable_for_days = form.cleaned_data['disable_for_days']
        if disable_for_days:
            disable_until = datetime.utcnow() + timedelta(days=disable_for_days)
            couch_user.two_factor_auth_disabled_until = disable_until
            couch_user.save()

        verification = form.cleaned_data['verification_mode']
        verified_by = form.cleaned_data['via_who'] or self.request.user.username
        change_messages = UserChangeMessage.two_factor_disabled_with_verification(
            verified_by, verification, disable_for_days)
        log_user_change(by_domain=None, for_domain=None, couch_user=couch_user,
                        changed_by_user=self.request.couch_user,
                        changed_via=USER_CHANGE_VIA_WEB, change_messages=change_messages,
                        by_domain_required_for_log=False,
                        for_domain_required_for_log=False)
        mail_admins(
            "Two-Factor account reset",
            "Two-Factor auth was reset. Details: \n"
            "    Account reset: {username}\n"
            "    Reset by: {reset_by}\n"
            "    Request Verification Mode: {verification}\n"
            "    Verified by: {verified_by}\n"
            "    Two-Factor disabled for {days} days.".format(
                username=username,
                reset_by=self.request.user.username,
                verification=verification,
                verified_by=verified_by,
                days=disable_for_days
            ),
        )
        send_HTML_email(
            "%sTwo-Factor authentication reset" % settings.EMAIL_SUBJECT_PREFIX,
            couch_user.get_email(),
            render_to_string('hqadmin/email/two_factor_reset_email.html', context={
                'until': disable_until.strftime('%Y-%m-%d %H:%M:%S UTC') if disable_for_days else None,
                'support_email': settings.SUPPORT_EMAIL,
                'email_subject': "[URGENT] Possible Account Breach",
                'email_body': "Two Factor Auth on my CommCare account "
                              "was disabled without my request. My username is: %s" % username,
            }),
        )

        messages.success(self.request, _('Two-Factor Auth successfully disabled.'))
        return redirect('{}?q={}'.format(reverse('web_user_lookup'), username))


class WebUserDataView(View):
    urlname = 'web_user_data'

    @method_decorator(check_lockout)
    @method_decorator(basicauth())
    def get(self, request, *args, **kwargs):
        couch_user = CouchUser.from_django_user(request.user)
        if couch_user.is_web_user():
            data = {'domains': couch_user.domains}
            return JsonResponse(data)
        else:
            return HttpResponse('Only web users can access this endpoint', status=400)


@method_decorator(require_superuser, name='dispatch')
class AppBuildTimingsView(TemplateView):
    template_name = 'hqadmin/app_build_timings.html'

    def get_context_data(self, **kwargs):
        context = super(AppBuildTimingsView, self).get_context_data(**kwargs)
        app_id = self.request.GET.get('app_id')
        if app_id:
            try:
                app = Application.get(app_id)
            except ResourceNotFound:
                raise Http404()
            timing_context = self.get_timing_context(app)
            context.update({
                'app': app,
                'timing_data': timing_context.to_list(),
            })
        return context

    @staticmethod
    def get_timing_context(app):
        # Intended to reproduce a live-preview app build
        # Contents should mirror the work done in the direct_ccz view
        with app.timing_context:
            errors = app.validate_app()
            assert not errors, errors

            app.set_media_versions()

            with app.timing_context("build_zip"):
                # mirroring the content of build_application_zip
                # but with the same `app` instance to preserve timing data
                fpath = create_files_for_ccz(
                    build=app,
                    build_profile_id=None,
                    include_multimedia_files=True,
                    include_index_files=True,
                    download_id=None,
                    compress_zip=True,
                    filename='app-profile-test.ccz',
                    download_targeted_version=False,
                    task=None,
                )

        os.remove(fpath)
        return app.timing_context


class OffboardingUserList(UserAdministration):
    urlname = 'get_offboarding_list'
    page_title = gettext_lazy("Get users to offboard")
    template_name = 'hqadmin/offboarding_list.html'

    def __init__(self):
        self.users = []
        self.table_title = ''
        self.validation_errors = []

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @property
    def page_context(self):
        form_data = self.request.POST if self.request.method == 'POST' else None
        if not self.users and not self.table_title:
            self.users = augmented_superusers(include_accounting_admin=True)
        return {
            'form': OffboardingUserListForm(data=form_data),
            'users': self.users,
            'table_title': _('All superusers and staff users') if not self.table_title else self.table_title,
            'validation_errors': self.validation_errors,
        }

    def post(self, request, *args, **kwargs):
        form = OffboardingUserListForm(self.request.POST)
        if form.is_valid():
            users = form.cleaned_data['csv_email_list']
            self.validation_errors = form.cleaned_data.get('validation_errors')
            if users:
                self.users = augmented_superusers(users=users, include_accounting_admin=True)
            else:
                self.users = users
            self.table_title = "Users that need their privileges revoked/account disabled"
            messages.success(request, _("Successfully retrieved users to offboard."))

        return self.get(request, *args, **kwargs)
