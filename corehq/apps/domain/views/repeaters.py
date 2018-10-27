from __future__ import absolute_import, unicode_literals
import csv342 as csv

from django.http import HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils.translation import ugettext as _

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
from corehq.apps.domain.utils import send_repeater_payloads

from corehq.apps.users.decorators import require_can_edit_web_users


@require_POST
@require_can_edit_web_users
def generate_repeater_payloads(request, domain):
    try:
        email_id = request.POST.get('email_id')
        repeater_id = request.POST.get('repeater_id')
        data = csv.reader(request.FILES['payload_ids_file'])
        payload_ids = [row[0] for row in data]
    except Exception as e:
        messages.error(request, _("Could not process the file. %s") % str(e))
    else:
        send_repeater_payloads.delay(repeater_id, payload_ids, email_id)
        messages.success(request, _("Successfully queued request. You should receive an email shortly."))
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))
