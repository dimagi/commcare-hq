from django.contrib import messages
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
from corehq.apps.integration.forms import DialerSettingsForm, SimprintsIntegrationForm
from corehq.apps.integration.models import DialerSettings
from corehq.apps.integration.util import get_dialer_settings
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions


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

