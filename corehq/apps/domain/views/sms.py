from django.urls import reverse
from django.utils.translation import gettext_lazy

from memoized import memoized

from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.smsbillables.async_handlers import (
    PublicSMSRatesAsyncHandler,
    SMSRatesAsyncHandler,
    SMSRatesSelect2AsyncHandler,
)
from corehq.apps.smsbillables.forms import (
    PublicSMSRateCalculatorForm,
    SMSRateCalculatorForm,
)


class PublicSMSRatesView(BasePageView, AsyncHandlerMixin):
    urlname = 'public_sms_rates_view'
    page_title = gettext_lazy("SMS Rate Calculator")
    template_name = 'domain/admin/bootstrap3/global_sms_rates.html'
    async_handlers = [PublicSMSRatesAsyncHandler]

    def dispatch(self, request, *args, **kwargs):
        return super(PublicSMSRatesView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def page_context(self):
        return {
            'rate_calc_form': PublicSMSRateCalculatorForm()
        }

    def post(self, request, *args, **kwargs):
        return self.async_response or self.get(request, *args, **kwargs)


class SMSRatesView(BaseAdminProjectSettingsView, AsyncHandlerMixin):
    urlname = 'domain_sms_rates_view'
    page_title = gettext_lazy("SMS Rate Calculator")
    template_name = 'domain/admin/bootstrap3/sms_rates.html'
    async_handlers = [
        SMSRatesAsyncHandler,
        SMSRatesSelect2AsyncHandler,
    ]

    def dispatch(self, request, *args, **kwargs):
        return super(SMSRatesView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def rate_calc_form(self):
        if self.request.method == 'POST':
            return SMSRateCalculatorForm(self.domain, self.request.POST)
        return SMSRateCalculatorForm(self.domain)

    @property
    def page_context(self):
        return {
            'rate_calc_form': self.rate_calc_form,
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        return self.get(request, *args, **kwargs)
