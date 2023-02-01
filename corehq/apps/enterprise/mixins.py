from memoized import memoized

from django.contrib import messages
from django.http import (
    HttpResponseRedirect,
)
from django.utils.translation import gettext as _

from corehq.apps.enterprise.models import (
    EnterpriseMobileWorkerSettings,
)
from corehq.apps.accounting.models import (
    BillingAccount,
)

from corehq.apps.enterprise.forms import (
    EnterpriseManageMobileWorkersForm,
)


class ManageMobileWorkersMixin:

    @property
    def page_context(self):
        return {
            'account': self.account,
            'edit_emw_settings_form': self.edit_emw_settings_form,
        }

    @property
    @memoized
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    @property
    @memoized
    def edit_emw_settings_form(self):
        emw_settings, _ = EnterpriseMobileWorkerSettings.objects.get_or_create(
            account=self.account,
        )
        if self.request.method == 'POST':
            return EnterpriseManageMobileWorkersForm(
                self.request.POST, emw_settings=emw_settings, domain=self.domain
            )
        return EnterpriseManageMobileWorkersForm(
            emw_settings=emw_settings, domain=self.domain
        )

    def post(self, request, *args, **kwargs):
        if self.edit_emw_settings_form.is_valid():
            self.edit_emw_settings_form.update_settings()
            messages.success(request, _("Settings have been updated!"))
            return HttpResponseRedirect(self.page_url)
        messages.error(
            request,
            _("Please check form for errors.")
        )
        return self.get(request, *args, **kwargs)
