from __future__ import absolute_import, unicode_literals

from django.urls import reverse
from django.utils.translation import ugettext_lazy

from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
    enable_case_search,
    disable_case_search,
)
from corehq.apps.hqwebapp.decorators import (
    use_jquery_ui,
    use_select2,
    use_select2_v4,
    use_multiselect,
)
from corehq.apps.accounting.exceptions import (
    NewSubscriptionError,
    PaymentRequestError,
    SubscriptionAdjustmentError,
)
from corehq.apps.accounting.payment_handlers import (
    BulkStripePaymentHandler,
    CreditStripePaymentHandler,
    InvoiceStripePaymentHandler,
)
from corehq.apps.accounting.utils import (
    get_change_status, get_privileges, fmt_dollar_amount,
    quantize_accounting_decimal, get_customer_cards,
    log_accounting_error, domain_has_privilege, is_downgrade
)
from corehq.apps.accounting.models import (
    Subscription, CreditLine, SubscriptionType,
    DefaultProductPlan, SoftwarePlanEdition, BillingAccount,
    BillingAccountType,
    Invoice, BillingRecord, InvoicePdf, PaymentMethodType,
    EntryPoint, WireInvoice, CustomerInvoice,
    StripePaymentMethod, LastPayment,
    UNLIMITED_FEATURE_USAGE, MINIMUM_SUBSCRIPTION_LENGTH
)
from corehq.apps.accounting.user_text import (
    get_feature_name,
    DESC_BY_EDITION,
    get_feature_recurring_interval,
)
from corehq.apps.domain.decorators import (
    domain_admin_required, login_required, require_superuser, login_and_domain_required
)
from corehq.apps.domain.forms import (
    DomainGlobalSettingsForm, DomainMetadataForm, SnapshotSettingsForm,
    SnapshotApplicationForm, DomainInternalForm, PrivacySecurityForm,
    ConfirmNewSubscriptionForm, ProBonoForm, EditBillingAccountInfoForm,
    ConfirmSubscriptionRenewalForm, SnapshotFixtureForm, TransferDomainForm,
    SelectSubscriptionTypeForm, INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS, AdvancedExtendedTrialForm,
    ContractedPartnerForm, DimagiOnlyEnterpriseForm, USE_PARENT_LOCATION_CHOICE,
    USE_LOCATION_CHOICE)
from corehq.apps.domain.models import (
    Domain,
    LICENSES,
    TransferDomainRequest,
)
from corehq.apps.domain.views.accounting import DomainAccountingSettings, DomainSubscriptionView
from corehq.apps.hqwebapp.views import BasePageView
from memoized import memoized



class ProBonoMixin(object):
    page_title = ugettext_lazy("Pro-Bono Application")
    is_submitted = False

    url_name = None

    @property
    def requesting_domain(self):
        raise NotImplementedError

    @property
    @memoized
    def pro_bono_form(self):
        if self.request.method == 'POST':
            return ProBonoForm(self.use_domain_field, self.request.POST)
        return ProBonoForm(self.use_domain_field)

    @property
    def page_context(self):
        return {
            'pro_bono_form': self.pro_bono_form,
            'is_submitted': self.is_submitted,
        }

    @property
    def page_url(self):
        return self.url_name

    def post(self, request, *args, **kwargs):
        if self.pro_bono_form.is_valid():
            self.pro_bono_form.process_submission(domain=self.requesting_domain)
            self.is_submitted = True
        return self.get(request, *args, **kwargs)


class ProBonoStaticView(ProBonoMixin, BasePageView):
    template_name = 'domain/pro_bono/static.html'
    urlname = 'pro_bono_static'
    use_domain_field = True

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(ProBonoStaticView, self).dispatch(request, *args, **kwargs)

    @property
    def requesting_domain(self):
        return self.pro_bono_form.cleaned_data['domain']


class ProBonoView(ProBonoMixin, DomainAccountingSettings):
    template_name = 'domain/pro_bono/domain.html'
    urlname = 'pro_bono'
    use_domain_field = False

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(ProBonoView, self).dispatch(request, *args, **kwargs)

    @property
    def requesting_domain(self):
        return self.domain

    @property
    def parent_pages(self):
        return [
            {
                'title': DomainSubscriptionView.page_title,
                'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
            }
        ]

    @property
    def section_url(self):
        return self.page_url
