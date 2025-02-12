from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from corehq import toggles
from corehq.apps.domain.decorators import login_required
from corehq.apps.domain.views.base import BaseDomainView
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.integration.kyc.forms import KycConfigureForm
from corehq.apps.integration.kyc.models import KycConfig
from corehq.util.htmx_action import HqHtmxActionMixin


@method_decorator(login_required, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycConfigurationView(BaseDomainView, HqHtmxActionMixin):
    section_name = _("Data")
    urlname = 'kyc_configuration'
    template_name = 'kyc/kyc_config_base.html'
    page_title = _('KYC Configuration')

    form_class = KycConfigureForm
    form_template_partial_name = 'kyc/partials/kyc_config_form_partial.html'

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))

    @property
    def page_context(self):
        return {
            'kyc_config_form': self.config_form,
        }

    @property
    def config(self):
        try:
            # Currently a domain can only save one config so we shouldn't
            # expect more than one per domain
            return KycConfig.objects.get(domain=self.domain)
        except KycConfig.DoesNotExist:
            return KycConfig(domain=self.domain)

    @property
    def config_form(self):
        if self.request.method == 'POST':
            return self.form_class(self.request.POST, instance=self.config)
        return self.form_class(instance=self.config)

    def post(self, request, *args, **kwargs):
        form = self.config_form
        show_success = False
        if form.is_valid():
            form.save(commit=True)
            show_success = True

        context = {
            'kyc_config_form': form,
            'show_success': show_success,
        }
        return self.render_htmx_partial_response(request, self.form_template_partial_name, context)


@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.KYC_VERIFICATION.required_decorator(), name='dispatch')
class KycVerificationReportView(BaseDomainView):
    urlname = 'kyc_verify'
    template_name = 'kyc/kyc_verify_report.html'
    section_name = _("Data")
    page_title = _('KYC Report')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def section_url(self):
        return reverse(self.urlname, args=(self.domain,))
