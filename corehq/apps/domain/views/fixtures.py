from __future__ import absolute_import, unicode_literals

from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq import toggles
from corehq.apps.calendar_fixture.forms import CalendarFixtureForm
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
    enable_case_search,
    disable_case_search,
)
from corehq.apps.locations.forms import LocationFixtureForm
from corehq.apps.locations.models import LocationFixtureConfiguration
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
from corehq.apps.domain.views.settings import BaseAdminProjectSettingsView



class CalendarFixtureConfigView(BaseAdminProjectSettingsView):
    urlname = 'calendar_fixture_config'
    page_title = ugettext_lazy('Calendar Fixture')
    template_name = 'domain/admin/calendar_fixture.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.CUSTOM_CALENDAR_FIXTURE.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(CalendarFixtureConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        calendar_settings = CalendarFixtureSettings.for_domain(self.domain)
        form = CalendarFixtureForm(request.POST, instance=calendar_settings)
        if form.is_valid():
            form.save()
            messages.success(request, _("Calendar configuration updated successfully"))

        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        calendar_settings = CalendarFixtureSettings.for_domain(self.domain)
        form = CalendarFixtureForm(instance=calendar_settings)
        return {'form': form}


class LocationFixtureConfigView(BaseAdminProjectSettingsView):
    urlname = 'location_fixture_config'
    page_title = ugettext_lazy('Location Fixture')
    template_name = 'domain/admin/location_fixture.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.HIERARCHICAL_LOCATION_FIXTURE.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(LocationFixtureConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        location_settings = LocationFixtureConfiguration.for_domain(self.domain)
        form = LocationFixtureForm(request.POST, instance=location_settings)
        if form.is_valid():
            form.save()
            messages.success(request, _("Location configuration updated successfully"))

        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        location_settings = LocationFixtureConfiguration.for_domain(self.domain)
        form = LocationFixtureForm(instance=location_settings)
        return {'form': form}
