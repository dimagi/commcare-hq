from __future__ import absolute_import
from __future__ import unicode_literals

from memoized import memoized

from django.contrib import messages
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq import toggles
from corehq.apps.domain.views import BaseAdminProjectSettingsView
from corehq.apps.integration.forms import SimprintsIntegrationForm
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
