from __future__ import absolute_import, unicode_literals
import copy
import datetime
from collections import defaultdict, namedtuple
from decimal import Decimal
import logging
import json
import io
import csv342 as csv

from couchdbkit import ResourceNotFound
import dateutil
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET
from django.views.generic import View
from django.db.models import Sum
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth.views import password_reset_confirm
from django.views.decorators.http import require_POST
from PIL import Image
from django.utils.translation import ugettext as _, ugettext_lazy
from django.contrib.auth.models import User

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.calendar_fixture.forms import CalendarFixtureForm
from corehq.apps.calendar_fixture.models import CalendarFixtureSettings
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    FuzzyProperties,
    IgnorePatterns,
    enable_case_search,
    disable_case_search,
)
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster
from corehq.apps.linked_domain.dbaccessors import get_domain_master_link
from corehq.apps.locations.permissions import location_safe
from corehq.apps.locations.forms import LocationFixtureForm
from corehq.apps.locations.models import LocationFixtureConfiguration
from corehq.const import USER_DATE_FORMAT
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.invoicing import DomainWireInvoiceFactory
from corehq.apps.hqwebapp.tasks import send_mail_async
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
from corehq.apps.accounting.subscription_changes import DomainDowngradeStatusHandler
from corehq.apps.accounting.forms import EnterprisePlanContactForm, AnnualPlanContactForm
from corehq.apps.accounting.utils import (
    get_change_status, get_privileges, fmt_dollar_amount,
    quantize_accounting_decimal, get_customer_cards,
    log_accounting_error, domain_has_privilege, is_downgrade
)
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.smsbillables.async_handlers import SMSRatesAsyncHandler, SMSRatesSelect2AsyncHandler
from corehq.apps.smsbillables.forms import SMSRateCalculatorForm
from corehq.apps.toggle_ui.views import ToggleEditView
from corehq.apps.users.models import Invitation, CouchUser, Permissions
from corehq.apps.fixtures.models import FixtureDataType
from corehq.toggles import NAMESPACE_DOMAIN, all_toggles, CAN_EDIT_EULA, TRANSFER_DOMAIN, NAMESPACE_USER
from custom.openclinica.forms import OpenClinicaSettingsForm
from custom.openclinica.models import OpenClinicaSettings
from dimagi.utils.couch.resource_conflict import retry_resource
from dimagi.utils.web import json_request
from corehq import privileges, feature_previews
from django_prbac.utils import has_privilege
from corehq.apps.accounting.models import (
    Subscription, CreditLine, SubscriptionType,
    DefaultProductPlan, SoftwarePlanEdition, BillingAccount,
    BillingAccountType,
    Invoice, BillingRecord, InvoicePdf, PaymentMethodType,
    EntryPoint, WireInvoice, CustomerInvoice,
    StripePaymentMethod, LastPayment,
    UNLIMITED_FEATURE_USAGE, MINIMUM_SUBSCRIPTION_LENGTH
)
from corehq.apps.accounting.usage import FeatureUsageCalculator
from corehq.apps.accounting.user_text import (
    get_feature_name,
    DESC_BY_EDITION,
    get_feature_recurring_interval,
)
from corehq.apps.domain.calculations import CALCS, CALC_FNS, CALC_ORDER, dom_calc
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
from corehq.apps.domain.utils import normalize_domain_name, send_repeater_payloads
from corehq.apps.hqwebapp.views import BaseSectionPageView, BasePageView, CRUDPaginatedViewMixin
from corehq.apps.domain.forms import ProjectSettingsForm
from memoized import memoized
from dimagi.utils.web import get_ip, json_response, get_site_domain

from corehq.apps.users.decorators import require_can_edit_web_users, require_permission
from toggle.models import Toggle
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.hqwebapp.signals import clear_login_attempts
from corehq.apps.ota.models import MobileRecoveryMeasure
import six
from six.moves import map


# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator
@login_required
def select(request, domain_select_template='domain/select.html', do_not_redirect=False):
    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain')

    email = request.couch_user.get_email()
    open_invitations = [e for e in Invitation.by_email(email) if not e.is_expired]

    additional_context = {
        'domains_for_user': domains_for_user,
        'open_invitations': open_invitations,
        'current_page': {'page_name': _('Select A Project')},
    }

    last_visited_domain = request.session.get('last_visited_domain')
    if open_invitations \
       or do_not_redirect \
       or not last_visited_domain:
        return render(request, domain_select_template, additional_context)
    else:
        domain = Domain.get_by_name(last_visited_domain)
        if domain and domain.is_active:
            # mirrors logic in login_and_domain_required
            if (
                request.couch_user.is_member_of(domain)
                or (request.user.is_superuser and not domain.restrict_superusers)
                or domain.is_snapshot
            ):
                try:
                    from corehq.apps.dashboard.views import dashboard_default
                    return dashboard_default(request, last_visited_domain)
                except Http404:
                    pass

        del request.session['last_visited_domain']
        return render(request, domain_select_template, additional_context)


class DomainViewMixin(object):
    """
        Paving the way for a world of entirely class-based views.
        Let's do this, guys. :-)

        Set strict_domain_fetching to True in subclasses to bypass the cache.
    """
    strict_domain_fetching = False

    @property
    @memoized
    def domain(self):
        domain = self.args[0] if len(self.args) > 0 else self.kwargs.get('domain', "")
        return normalize_domain_name(domain)

    @property
    @memoized
    def domain_object(self):
        domain = Domain.get_by_name(self.domain, strict=self.strict_domain_fetching)
        if not domain:
            raise Http404()
        return domain


class LoginAndDomainMixin(object):

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)


class BaseDomainView(LoginAndDomainMixin, BaseSectionPageView, DomainViewMixin):

    @property
    def main_context(self):
        main_context = super(BaseDomainView, self).main_context
        main_context.update({
            'domain': self.domain,
        })
        return main_context

    @property
    @memoized
    def page_url(self):
        if self.urlname:
            return reverse(self.urlname, args=[self.domain])


