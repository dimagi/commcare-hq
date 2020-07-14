from django.contrib import messages
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from corehq.apps.domain.decorators import login_and_domain_required

from corehq.apps.domain.views.settings import BaseProjectSettingsView
from django.utils.translation import ugettext_lazy

from corehq.apps.domain.models import Domain
from corehq.apps.widget.forms import DialerSettingsForm
from corehq.apps.widget.models import DialerSettings
from corehq.apps.widget.util import get_dialer_settings
from corehq import toggles

from memoized import memoized


@toggles.WIDGET_DIALER.required_decorator()
@login_and_domain_required
@require_GET
def dialer_view(request, domain):
    callout_number = request.GET.get("callout_number")
    dialer_settings = get_dialer_settings(domain)
    return render(request, "widget/web_app_dialer.html", {"callout_number": callout_number,
                                                          "dialer_settings": dialer_settings,
                                                          })


class DialerSettingsView(BaseProjectSettingsView):
    urlname = 'dialer_settings_view'
    page_title = ugettext_lazy('Dialer Settings')
    template_name = 'widget/settings.html'

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
