from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import itertools
import uuid
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.mail import mail_admins
from django.http import (
    HttpResponseRedirect,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    JsonResponse,
    StreamingHttpResponse,
)
from django.http.response import Http404
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy, ugettext as _
from django.views.generic import FormView, TemplateView, View
from lxml import etree
from lxml.builder import E

from casexml.apps.phone.xml import SYNC_XMLNS
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from corehq.apps.domain.auth import basicauth
from corehq.apps.domain.decorators import (
    require_superuser, require_superuser_or_contractor,
    login_or_basic, domain_admin_required,
    check_lockout)
from corehq.apps.ota.views import get_restore_response, get_restore_params
from corehq.apps.hqwebapp.decorators import use_datatables, use_jquery_ui, \
    use_nvd3_v3
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser
from corehq.apps.users.util import format_username
from corehq.form_processor.serializers import XFormInstanceSQLRawDocSerializer, \
    CommCareCaseSQLRawDocSerializer
from corehq.util import reverse
from corehq.util.supervisord.api import (
    PillowtopSupervisorApi,
    SupervisorException,
    all_pillows_supervisor_status,
    pillow_supervisor_status
)
from corehq.util.timer import TimingContext
from couchforms.openrosa_response import RESPONSE_XMLNS
from dimagi.utils.django.email import send_HTML_email
from corehq.apps.hqadmin.forms import (
    AuthenticateAsForm, BrokenBuildsForm, EmailForm, SuperuserManagementForm,
    ReprocessMessagingCaseUpdatesForm,
    DisableTwoFactorForm, DisableUserForm)
from corehq.apps.hqadmin.views.utils import BaseAdminSectionView
from six.moves import filter


class UserAdministration(BaseAdminSectionView):
    section_name = ugettext_lazy("User Administration")


class AuthenticateAs(UserAdministration):
    urlname = 'authenticate_as'
    page_title = _("Login as Other User")
    template_name = 'hqadmin/authenticate_as.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(AuthenticateAs, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        return {
            'hide_filters': True,
            'form': AuthenticateAsForm(initial=self.request.POST),
            'root_page_url': reverse('authenticate_as'),
        }

    def post(self, request, *args, **kwargs):
        form = AuthenticateAsForm(self.request.POST)
        if form.is_valid():
            request.user = User.objects.get(username=form.full_username)

            # http://stackoverflow.com/a/2787747/835696
            # This allows us to bypass the authenticate call
            request.user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, request.user)
            return HttpResponseRedirect('/')
        all_errors = form.errors.pop('__all__', None)
        if all_errors:
            messages.error(request, ','.join(all_errors))
        if form.errors:
            messages.error(request, form.errors)
        return self.get(request, *args, **kwargs)


class SuperuserManagement(UserAdministration):
    urlname = 'superuser_management'
    page_title = _("Grant or revoke superuser access")
    template_name = 'hqadmin/superuser_management.html'

    @method_decorator(require_superuser)
    def dispatch(self, *args, **kwargs):
        return super(SuperuserManagement, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        # only staff can toggle is_staff
        can_toggle_is_staff = self.request.user.is_staff
        # render validation errors if rendered after POST
        args = [can_toggle_is_staff, self.request.POST] if self.request.POST else [can_toggle_is_staff]
        return {
            'form': SuperuserManagementForm(*args)
        }

    def post(self, request, *args, **kwargs):
        can_toggle_is_staff = request.user.is_staff
        form = SuperuserManagementForm(can_toggle_is_staff, self.request.POST)
        if form.is_valid():
            users = form.cleaned_data['users']
            is_superuser = 'is_superuser' in form.cleaned_data['privileges']
            is_staff = 'is_staff' in form.cleaned_data['privileges']

            for user in users:
                # save user object only if needed and just once
                should_save = False
                if user.is_superuser is not is_superuser:
                    user.is_superuser = is_superuser
                    should_save = True

                if can_toggle_is_staff and user.is_staff is not is_staff:
                    user.is_staff = is_staff
                    should_save = True

                if should_save:
                    user.save()
            messages.success(request, _("Successfully updated superuser permissions"))

        return self.get(request, *args, **kwargs)


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
            return HttpResponseBadRequest('Please specify a user using ?as=user@domain')

        username, domain = full_username.split('@')
        if not domain.endswith(settings.HQ_ACCOUNT_ROOT):
            full_username = format_username(username, domain)

        self.user = CommCareUser.get_by_username(full_username)
        if not self.user:
            return HttpResponseNotFound('User %s not found.' % full_username)

        if not self._validate_user_access(self.user):
            raise Http404()

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
        return get_restore_response(
            self.user.domain, self.user, app_id=self.app_id,
            **get_restore_params(self.request)
        )

    def get_context_data(self, **kwargs):
        context = super(AdminRestoreView, self).get_context_data(**kwargs)
        response, timing_context = self._get_restore_response()
        timing_context = timing_context or TimingContext(self.user.username)
        if isinstance(response, StreamingHttpResponse):
            string_payload = b''.join(response.streaming_content)
            xml_payload = etree.fromstring(string_payload)
            restore_id_element = xml_payload.find('{{{0}}}Sync/{{{0}}}restore_id'.format(SYNC_XMLNS))
            cases = xml_payload.findall('{http://commcarehq.org/case/transaction/v2}case')
            num_cases = len(cases)

            create_case_type = filter(None, [case.find(
                '{http://commcarehq.org/case/transaction/v2}create/'
                '{http://commcarehq.org/case/transaction/v2}case_type'
            ) for case in cases])
            update_case_type = filter(None, [case.find(
                '{http://commcarehq.org/case/transaction/v2}update/'
                '{http://commcarehq.org/case/transaction/v2}case_type'
            ) for case in cases])
            case_type_counts = dict(Counter([
                case.type for case in itertools.chain(create_case_type, update_case_type)
            ]))

            locations = xml_payload.findall(
                "{{{0}}}fixture[@id='locations']/{{{0}}}locations/{{{0}}}location".format(RESPONSE_XMLNS)
            )
            num_locations = len(locations)
            location_type_counts = dict(Counter(location.attrib['type'] for location in locations))

            reports = xml_payload.findall(
                "{{{0}}}fixture[@id='commcare:reports']/{{{0}}}reports/".format(RESPONSE_XMLNS)
            )
            num_reports = len(reports)
            report_row_counts = {
                report.attrib['report_id']: len(report.findall('{{{0}}}rows/{{{0}}}row'.format(RESPONSE_XMLNS)))
                for report in reports
                if 'report_id' in report.attrib
            }

            num_ledger_entries = len(xml_payload.findall(
                "{{{0}}}balance/{{{0}}}entry".format(COMMTRACK_REPORT_XMLNS)
            ))
        else:
            if response.status_code in (401, 404):
                # corehq.apps.ota.views.get_restore_response couldn't find user or user didn't have perms
                xml_payload = E.error(response.content)
            elif response.status_code == 412:
                # RestoreConfig.get_response returned HttpResponse 412. Response content is already XML
                xml_payload = etree.fromstring(response.content)
            else:
                message = _('Unexpected restore response {}: {}. '
                            'If you believe this is a bug please report an issue.').format(response.status_code,
                                                                                           response.content)
                xml_payload = E.error(message)
            restore_id_element = None
            num_cases = 0
            case_type_counts = {}
            num_locations = 0
            location_type_counts = {}
            num_reports = 0
            report_row_counts = {}
            num_ledger_entries = 0
        formatted_payload = etree.tostring(xml_payload, pretty_print=True)
        hide_xml = self.request.GET.get('hide_xml') == 'true'
        context.update({
            'payload': formatted_payload,
            'restore_id': restore_id_element.text if restore_id_element is not None else None,
            'status_code': response.status_code,
            'timing_data': timing_context.to_list(),
            'num_cases': num_cases,
            'num_locations': num_locations,
            'num_reports': num_reports,
            'hide_xml': hide_xml,
            'case_type_counts': case_type_counts,
            'location_type_counts': location_type_counts,
            'report_row_counts': report_row_counts,
            'num_ledger_entries': num_ledger_entries,
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
        return self.domain == user.domain


@require_superuser
def web_user_lookup(request):
    template = "hqadmin/web_user_lookup.html"
    web_user_email = request.GET.get("q")
    if not web_user_email:
        return render(request, template, {})

    web_user = WebUser.get_by_username(web_user_email)
    context = {
        'audit_report_url': reverse('admin_report_dispatcher', args=('user_audit_report',))
    }
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
        return '{}?q={}'.format(reverse('web_user_lookup'), self.username)

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
        if not self.user:
            return self.redirect_response(self.request)

        reset_password = form.cleaned_data['reset_password']
        if reset_password:
            self.user.set_password(uuid.uuid4().hex)

        # toggle active state
        self.user.is_active = not self.user.is_active
        self.user.save()

        verb = 're-enabled' if self.user.is_active else 'disabled'
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
                reason=form.cleaned_data['reason'],
            )
        )
        send_HTML_email(
            "%sYour account has been %s" % (settings.EMAIL_SUBJECT_PREFIX, verb),
            self.username,
            render_to_string('hqadmin/email/account_disabled_email.html', context={
                'support_email': settings.SUPPORT_EMAIL,
                'password_reset': reset_password,
                'user': self.user,
                'verb': verb,
                'reason': form.cleaned_data['reason'],
            }),
        )

        messages.success(self.request, _('Account successfully %(verb)s.' % {'verb': verb}))
        return redirect('{}?q={}'.format(reverse('web_user_lookup'), self.username))


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

        disable_for_days = form.cleaned_data['disable_for_days']
        if disable_for_days:
            couch_user = CouchUser.from_django_user(user)
            disable_until = datetime.utcnow() + timedelta(days=disable_for_days)
            couch_user.two_factor_auth_disabled_until = disable_until
            couch_user.save()

        mail_admins(
            "Two-Factor account reset",
            "Two-Factor auth was reset. Details: \n"
            "    Account reset: {username}\n"
            "    Reset by: {reset_by}\n"
            "    Request Verificatoin Mode: {verification}\n"
            "    Verified by: {verified_by}\n"
            "    Two-Factor disabled for {days} days.".format(
                username=username,
                reset_by=self.request.user.username,
                verification=form.cleaned_data['verification_mode'],
                verified_by=form.cleaned_data['via_who'] or self.request.user.username,
                days=disable_for_days
            ),
        )
        send_HTML_email(
            "%sTwo-Factor authentication reset" % settings.EMAIL_SUBJECT_PREFIX,
            username,
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
