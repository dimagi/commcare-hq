import requests
from requests.exceptions import RequestException
from uuid import uuid4

from django.contrib import messages
from django.http.response import Http404
from django.views.decorators.http import require_POST
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.views import BaseAdminProjectSettingsView
from corehq.apps.domain.views.settings import BaseProjectSettingsView
from corehq.apps.integration.forms import (
    DialerSettingsForm,
    HmacCalloutSettingsForm,
    GaenOtpServerSettingsForm,
    SimprintsIntegrationForm,
)
from corehq.apps.integration.models import DialerSettings, GaenOtpServerSettings, HmacCalloutSettings
from corehq.apps.integration.util import get_dialer_settings, get_gaen_otp_server_settings
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class BiometricIntegrationView(BaseAdminProjectSettingsView):
    urlname = 'biometric_integration'
    page_title = ugettext_lazy("Biometric Integration")
    template_name = 'integration/biometric.html'

    @method_decorator(require_permission(Permissions.edit_motech))
    @method_decorator(toggles.BIOMETRIC_INTEGRATION.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(BiometricIntegrationView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def simprints_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return SimprintsIntegrationForm(
            data, domain=self.domain
        )

    @property
    def page_context(self):
        return {
            'simprints_form': self.simprints_form
        }

    def post(self, request, *args, **kwargs):
        if self.simprints_form.is_valid():
            self.simprints_form.save()
            messages.success(
                request, _("Biometric Integration settings have been updated.")
            )
        else:
            messages.error(
                request, _("Could not update Biometric Integration settings.")
            )
        return self.get(request, *args, **kwargs)


@toggles.WIDGET_DIALER.required_decorator()
@login_and_domain_required
@require_GET
def dialer_view(request, domain):
    callout_number = request.GET.get("callout_number")
    dialer_settings = get_dialer_settings(domain)
    return render(request, "integration/web_app_dialer.html", {"callout_number": callout_number,
                                                               "dialer_settings": dialer_settings,
                                                               })


@toggles.GAEN_OTP_SERVER.required_decorator()
@login_and_domain_required
@require_POST
def gaen_otp_view(request, domain):
    request_error_msg = None
    try:
        post_data = get_post_data_for_otp(request, domain)

        try:
            case_id = request.POST['case_id']

            case = CaseAccessors(domain).get_case(case_id)

            case_name = case.name

        except KeyError:
            raise InvalidOtpRequestException(_("OTP Request missing a required argument 'case_id'"))
        except CaseNotFound:
            raise Http404(_("No matching patient record found"))

        if request.POST.get('dummy_code'):
            otp_data = {"code": request.POST['dummy_code']}
        else:
            otp_data = get_otp_response(post_data, get_gaen_otp_server_settings(domain))

        styled_otp_code = " ".join(otp_data['code'][i:i + 2] for i in range(0, len(otp_data['code']), 2))

        return render(request, "integration/web_app_gaen_otp.html", {"otp_data": otp_data,
                                                                     "styled_otp_code": styled_otp_code,
                                                                     "case_name": case_name,
                                                                     })
    except RequestException:
        request_error_msg = _("""We are having problems communicating with the Exposure Nofication server
                                 please try again later""")
    except InvalidOtpRequestException as e:
        request_error_msg = e.message

    return render(request, "integration/web_app_integration_err.html", {"error_msg": request_error_msg})


def get_otp_response(post_data, gaen_otp_settings):
    headers = {"Authorization": "Bearer %s" % gaen_otp_settings.auth_token}
    otp_response = requests.post(gaen_otp_settings.server_url,
                                 data=post_data,
                                 headers=headers)

    if otp_response.status_code == 400:
        raise InvalidOtpRequestException(otp_response.text)

    if otp_response.status_code == 500:
        raise RequestException(None, None, "Error on OTP Server")

    try:
        return {
            'code': otp_response.json()['code']
        }
    except Exception:
        raise RequestException(None, None, "Invalid OTP Response from Notification Server")


class InvalidOtpRequestException(Exception):
    def __init__(self, message):
        self.message = message


def get_post_data_for_otp(request, domain):
    post_params = {
        'jobId': str(uuid4()),
    }

    property_map = {
        'phone_number': 'mobile',
        'test_date': 'testDate',
        'onset_date': 'onsetDate',
        'test_type': 'testType',
        }
    for request_param in property_map:
        if request_param in request.POST:
            post_params[property_map[request_param]] = request.POST[request_param]

    return post_params


class DialerSettingsView(BaseProjectSettingsView):
    urlname = 'dialer_settings_view'
    page_title = ugettext_lazy('Dialer Settings')
    template_name = 'integration/dialer_settings.html'

    @method_decorator(toggles.WIDGET_DIALER.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(DialerSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def dialer_settings_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return DialerSettingsForm(
            data, domain=self.domain
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        kwargs['initial'] = DialerSettings.objects.get_or_create(domain=self.domain)
        return kwargs

    @property
    def page_context(self):
        return {
            'form': self.dialer_settings_form
        }

    def post(self, request, *args, **kwargs):
        if self.dialer_settings_form.is_valid():
            self.dialer_settings_form.save()
            messages.success(
                request, ugettext_lazy("Dialer Settings Updated")
            )
        else:
            messages.error(
                request, ugettext_lazy("Could not update Dialer Settings")
            )
        return self.get(request, *args, **kwargs)


@method_decorator(toggles.GAEN_OTP_SERVER.required_decorator(), name='dispatch')
class GaenOtpServerSettingsView(BaseProjectSettingsView):
    urlname = 'gaen_otp_server_settings_view'
    page_title = ugettext_lazy('GAEN OTP Server Config')
    template_name = 'integration/gaen_otp_server_settings.html'

    @property
    @memoized
    def gaen_otp_server_settings_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return GaenOtpServerSettingsForm(
            data, domain=self.domain
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        kwargs['initial'] = GaenOtpServerSettings.objects.get_or_create(domain=self.domain)
        return kwargs

    @property
    def page_context(self):
        return {
            'form': self.gaen_otp_server_settings_form
        }

    def post(self, request, *args, **kwargs):
        if self.gaen_otp_server_settings_form.is_valid():
            self.gaen_otp_server_settings_form.save()
            messages.success(
                request, ugettext_lazy("GAEN OTP Server Settings Updated")
            )
        else:
            messages.error(
                request, ugettext_lazy("Could not update GAEN OTP Server Settings")
            )
        return self.get(request, *args, **kwargs)


@method_decorator(toggles.HMAC_CALLOUT.required_decorator(), name='dispatch')
class HmacCalloutSettingsView(BaseProjectSettingsView):
    urlname = 'hmac_callout_settings_view'
    page_title = ugettext_lazy('Signed Callout Settings')
    template_name = 'integration/hmac_callout_settings.html'

    @property
    @memoized
    def hmac_callout_settings_form(self):
        data = self.request.POST if self.request.method == 'POST' else None
        return HmacCalloutSettingsForm(
            data, domain=self.domain
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['domain'] = self.domain
        kwargs['initial'] = HmacCalloutSettings.objects.get_or_create(domain=self.domain)
        return kwargs

    @property
    def page_context(self):
        return {
            'form': self.hmac_callout_settings_form
        }

    def post(self, request, *args, **kwargs):
        if self.hmac_callout_settings_form.is_valid():
            self.hmac_callout_settings_form.save()
            messages.success(
                request, ugettext_lazy("Callout Settings Updated")
            )
        else:
            messages.error(
                request, ugettext_lazy("Could not update Callout Settings")
            )
        return self.get(request, *args, **kwargs)
