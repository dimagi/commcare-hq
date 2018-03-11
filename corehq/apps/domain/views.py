from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import datetime
from decimal import Decimal
import logging
import json
import io
import csv

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
from corehq.apps.accounting.forms import EnterprisePlanContactForm
from corehq.apps.accounting.utils import (
    get_change_status, get_privileges, fmt_dollar_amount,
    quantize_accounting_decimal, get_customer_cards,
    log_accounting_error, domain_has_privilege,
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
    EntryPoint, WireInvoice,
    StripePaymentMethod, LastPayment,
    UNLIMITED_FEATURE_USAGE,
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
from corehq.motech.repeaters.forms import EmailBulkPayload
from corehq.apps.users.decorators import require_can_edit_web_users, require_permission
from toggle.models import Toggle
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.hqwebapp.signals import clear_login_attempts
import six
from six.moves import map


PAYMENT_ERROR_MESSAGES = {
    400: ugettext_lazy('Your request was not formatted properly.'),
    403: ugettext_lazy('Forbidden.'),
    404: ugettext_lazy('Page not found.'),
    500: ugettext_lazy("There was an error processing your request."
           " We're working quickly to fix the issue. Please try again shortly."),
}


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


class SubscriptionUpgradeRequiredView(LoginAndDomainMixin, BasePageView,
                                      DomainViewMixin):
    page_title = ugettext_lazy("Upgrade Required")
    template_name = "domain/insufficient_privilege_notification.html"

    @property
    def page_url(self):
        return self.request.get_full_path

    @property
    def page_name(self):
        return _("Sorry, you do not have access to %(feature_name)s") % {
            'feature_name': self.feature_name,
        }

    @property
    def is_domain_admin(self):
        if not hasattr(self.request, 'couch_user'):
            return False
        return self.request.couch_user.is_domain_admin(self.domain)

    @property
    def page_context(self):
        return {
            'domain': self.domain,
            'feature_name': self.feature_name,
            'plan_name': self.required_plan_name,
            'change_subscription_url': reverse(SelectPlanView.urlname,
                                               args=[self.domain]),
            'is_domain_admin': self.is_domain_admin,
        }

    @property
    def missing_privilege(self):
        return self.args[1]

    @property
    def feature_name(self):
        return privileges.Titles.get_name_from_privilege(self.missing_privilege)

    @property
    def required_plan_name(self):
        return DefaultProductPlan.get_lowest_edition([self.missing_privilege])

    def get(self, request, *args, **kwargs):
        self.request = request
        self.args = args
        return super(SubscriptionUpgradeRequiredView, self).get(
            request, *args, **kwargs
        )


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


class BaseProjectSettingsView(BaseDomainView):
    section_name = ugettext_lazy("Project Settings")
    template_name = "settings/base_template.html"

    @property
    def main_context(self):
        main_context = super(BaseProjectSettingsView, self).main_context
        main_context.update({
            'is_project_settings': True,
        })
        return main_context

    @property
    @memoized
    def section_url(self):
        return reverse(EditMyProjectSettingsView.urlname, args=[self.domain])


class DefaultProjectSettingsView(BaseDomainView):
    urlname = 'domain_settings_default'

    def get(self, request, *args, **kwargs):
        if request.couch_user.is_domain_admin(self.domain):
            return HttpResponseRedirect(reverse(EditBasicProjectInfoView.urlname, args=[self.domain]))
        return HttpResponseRedirect(reverse(EditMyProjectSettingsView.urlname, args=[self.domain]))


class BaseAdminProjectSettingsView(BaseProjectSettingsView):
    """
        The base class for all project settings views that require administrative
        access.
    """

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)


class BaseEditProjectInfoView(BaseAdminProjectSettingsView):
    """
        The base class for all the edit project information views.
    """
    strict_domain_fetching = True

    @property
    def autocomplete_fields(self):
        return []

    @property
    def main_context(self):
        context = super(BaseEditProjectInfoView, self).main_context
        context.update({
            'autocomplete_fields': self.autocomplete_fields,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            # ideally the template gets access to the domain doc through
            # some other means. otherwise it has to be supplied to every view reachable in that sidebar (every
            # view whose template extends users_base.html); mike says he's refactoring all of this imminently, so
            # i will not worry about it until he is done
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'cloudcare_releases':  self.domain_object.cloudcare_releases,
        })
        return context


class EditBasicProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_basic.html'
    urlname = 'domain_basic_info'
    page_title = ugettext_lazy("Basic")

    @method_decorator(domain_admin_required)
    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def can_user_see_meta(self):
        return self.request.couch_user.is_previewer()

    @property
    def can_use_custom_logo(self):
        return has_privilege(self.request, privileges.CUSTOM_BRANDING)

    @property
    @memoized
    def basic_info_form(self):
        initial = {
            'hr_name': self.domain_object.hr_name or self.domain_object.name,
            'project_description': self.domain_object.project_description,
            'default_timezone': self.domain_object.default_timezone,
            'case_sharing': json.dumps(self.domain_object.case_sharing),
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'call_center_type': self.initial_call_center_type,
            'call_center_case_owner': self.initial_call_center_case_owner,
            'call_center_case_type': self.domain_object.call_center_config.case_type,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            'mobile_ucr_sync_interval': self.domain_object.default_mobile_ucr_sync_interval
        }
        if self.can_user_see_meta:
            initial.update({
                'is_test': self.domain_object.is_test,
                'cloudcare_releases': self.domain_object.cloudcare_releases,
            })
            form_cls = DomainMetadataForm
        else:
            form_cls = DomainGlobalSettingsForm

        if self.request.method == 'POST':
            return form_cls(
                self.request.POST,
                self.request.FILES,
                domain=self.domain_object,
                can_use_custom_logo=self.can_use_custom_logo,
            )

        return form_cls(
            initial=initial,
            domain=self.domain_object,
            can_use_custom_logo=self.can_use_custom_logo
        )

    @property
    @memoized
    def initial_call_center_case_owner(self):
        config = self.domain_object.call_center_config
        if config.use_user_location_as_owner:
            if config.user_location_ancestor_level == 1:
                return USE_PARENT_LOCATION_CHOICE
            return USE_LOCATION_CHOICE
        return self.domain_object.call_center_config.case_owner_id

    @property
    @memoized
    def initial_call_center_type(self):
        if self.domain_object.call_center_config.use_fixtures:
            return DomainGlobalSettingsForm.CASES_AND_FIXTURES_CHOICE
        return DomainGlobalSettingsForm.CASES_ONLY_CHOICE

    @property
    def page_context(self):
        return {
            'basic_info_form': self.basic_info_form,
        }

    def post(self, request, *args, **kwargs):
        if self.basic_info_form.is_valid():
            if self.basic_info_form.save(request, self.domain_object):
                messages.success(request, _("Project settings saved!"))
            else:
                messages.error(request, _("There seems to have been an error saving your settings. Please try again!"))
            return HttpResponseRedirect(self.page_url)

        return self.get(request, *args, **kwargs)


class EditMyProjectSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/my_project_settings.html'
    urlname = 'my_project_settings'
    page_title = ugettext_lazy("My Timezone")

    @method_decorator(login_and_domain_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginAndDomainMixin, self).dispatch(*args, **kwargs)

    @property
    @memoized
    def my_project_settings_form(self):
        initial = { 'global_timezone': self.domain_object.default_timezone }
        if self.domain_membership:
            initial.update({
                'override_global_tz': self.domain_membership.override_global_tz,
                'user_timezone': (self.domain_membership.timezone if self.domain_membership.override_global_tz
                                  else self.domain_object.default_timezone),
            })
        else:
            initial.update({
                'override_global_tz': False,
                'user_timezone': initial["global_timezone"],
            })

        if self.request.method == 'POST':
            return ProjectSettingsForm(self.request.POST, initial=initial)
        return ProjectSettingsForm(initial=initial)

    @property
    @memoized
    def domain_membership(self):
        return self.request.couch_user.get_domain_membership(self.domain)

    @property
    def page_context(self):
        return {
            'my_project_settings_form': self.my_project_settings_form,
            'override_global_tz': self.domain_membership.override_global_tz if self.domain_membership else False,
            'no_domain_membership': not self.domain_membership,
        }

    def post(self, request, *args, **kwargs):
        if self.my_project_settings_form.is_valid():
            self.my_project_settings_form.save(self.request.couch_user, self.domain)
            messages.success(request, _("Your project settings have been saved!"))
        return self.get(request, *args, **kwargs)


class EditOpenClinicaSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/openclinica_settings.html'
    urlname = 'oc_settings'
    page_title = ugettext_lazy('OpenClinica settings')

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def openclinica_settings_form(self):
        oc_settings = OpenClinicaSettings.for_domain(self.domain_object.name)
        initial = dict(oc_settings.study) if oc_settings else {}
        if self.request.method == 'POST':
            return OpenClinicaSettingsForm(self.request.POST, initial=initial)
        return OpenClinicaSettingsForm(initial=initial)

    @property
    def page_context(self):
        return {'openclinica_settings_form': self.openclinica_settings_form}

    @method_decorator(sensitive_post_parameters('username', 'password'))
    def post(self, request, *args, **kwargs):
        if self.openclinica_settings_form.is_valid():
            if self.openclinica_settings_form.save(self.domain_object):
                messages.success(request, _('OpenClinica settings successfully updated'))
            else:
                messages.error(request, _('An error occurred. Please try again.'))
        return self.get(request, *args, **kwargs)


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


def autocomplete_fields(request, field):
    prefix = request.GET.get('prefix', '')
    results = Domain.field_by_prefix(field, prefix)
    return HttpResponse(json.dumps(results))


@location_safe
def logo(request, domain):
    logo = Domain.get_by_name(domain).get_custom_logo()
    if logo is None:
        raise Http404()

    return HttpResponse(logo[0], content_type=logo[1])


class DomainAccountingSettings(BaseProjectSettingsView):

    @method_decorator(require_permission(Permissions.edit_billing))
    def dispatch(self, request, *args, **kwargs):
        return super(DomainAccountingSettings, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    @property
    def current_subscription(self):
        return Subscription.get_active_subscription_by_domain(self.domain)


class DomainSubscriptionView(DomainAccountingSettings):
    urlname = 'domain_subscription_view'
    template_name = 'domain/current_subscription.html'
    page_title = ugettext_lazy("Current Subscription")

    @property
    def can_purchase_credits(self):
        return self.request.couch_user.can_edit_billing()

    @property
    @memoized
    def plan(self):
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()
        date_end = None
        next_subscription = {
            'exists': False,
            'can_renew': False,
            'name': None,
            'price': None,
        }
        cards = None
        if subscription:
            cards = get_customer_cards(self.request.user.username, self.domain)
            date_end = (subscription.date_end.strftime(USER_DATE_FORMAT)
                        if subscription.date_end is not None else "--")

            if subscription.date_end is not None:
                if subscription.is_renewed:
                    next_subscription.update({
                        'exists': True,
                        'date_start': subscription.next_subscription.date_start.strftime(USER_DATE_FORMAT),
                        'name': subscription.next_subscription.plan_version.plan.name,
                        'price': (
                            _("USD %s /month")
                            % subscription.next_subscription.plan_version.product_rate.monthly_fee
                        ),
                    })

                else:
                    days_left = (subscription.date_end - datetime.date.today()).days
                    next_subscription.update({
                        'can_renew': days_left <= 30,
                        'renew_url': reverse(SubscriptionRenewalView.urlname, args=[self.domain]),
                    })

        if subscription:
            credit_lines = CreditLine.get_non_general_credits_by_subscription(subscription)
            credit_lines = [cl for cl in credit_lines if cl.balance > 0]
            has_credits_in_non_general_credit_line = len(credit_lines) > 0
        else:
            has_credits_in_non_general_credit_line = False

        info = {
            'products': [self.get_product_summary(plan_version, self.account, subscription)],
            'features': self.get_feature_summary(plan_version, self.account, subscription),
            'general_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_by_subscription_and_features(
                    subscription
                ) if subscription else None
            )),
            'account_general_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_for_account(
                    self.account
                ) if self.account else None
            )),
            'css_class': "label-plan label-plan-%s" % plan_version.plan.edition.lower(),
            'do_not_invoice': subscription.do_not_invoice if subscription is not None else False,
            'is_trial': subscription.is_trial if subscription is not None else False,
            'date_start': (subscription.date_start.strftime(USER_DATE_FORMAT)
                           if subscription is not None else None),
            'date_end': date_end,
            'cards': cards,
            'next_subscription': next_subscription,
            'has_credits_in_non_general_credit_line': has_credits_in_non_general_credit_line
        }
        info['has_account_level_credit'] = (
            any(
                product_info['account_credit'] and product_info['account_credit']['is_visible']
                for product_info in info['products']
            )
            or info['account_general_credit'] and info['account_general_credit']['is_visible']
        )
        info.update(plan_version.user_facing_description)

        return info

    def _fmt_credit(self, credit_amount=None):
        if credit_amount is None:
            return {
                'amount': "--",
            }
        return {
            'amount': fmt_dollar_amount(credit_amount),
            'is_visible': credit_amount != Decimal('0.0'),
        }

    def _credit_grand_total(self, credit_lines):
        return sum([c.balance for c in credit_lines]) if credit_lines else Decimal('0.00')

    def get_product_summary(self, plan_version, account, subscription):
        product_rate = plan_version.product_rate
        return {
            'monthly_fee': _("USD %s /month") % product_rate.monthly_fee,
            'subscription_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_by_subscription_and_features(
                    subscription, is_product=True
                ) if subscription else None
            )),
            'account_credit': self._fmt_credit(self._credit_grand_total(
                CreditLine.get_credits_for_account(
                    account, is_product=True
                ) if account else None
            )),
        }

    def get_feature_summary(self, plan_version, account, subscription):
        def _get_feature_info(feature_rate):
            usage = FeatureUsageCalculator(feature_rate, self.domain).get_usage()
            feature_type = feature_rate.feature.feature_type
            if feature_rate.monthly_limit == UNLIMITED_FEATURE_USAGE:
                remaining = limit = _('Unlimited')
            else:
                limit = feature_rate.monthly_limit
                remaining = limit - usage
                if remaining < 0:
                    remaining = _("%d over limit") % (-1 * remaining)
            return {
                'name': get_feature_name(feature_type),
                'usage': usage,
                'limit': limit,
                'remaining': remaining,
                'type': feature_type,
                'recurring_interval': get_feature_recurring_interval(feature_type),
                'subscription_credit': self._fmt_credit(self._credit_grand_total(
                    CreditLine.get_credits_by_subscription_and_features(
                        subscription, feature_type=feature_type
                    ) if subscription else None
                )),
                'account_credit': self._fmt_credit(self._credit_grand_total(
                    CreditLine.get_credits_for_account(
                        account, feature_type=feature_type
                    ) if account else None
                )),
            }

        return list(map(_get_feature_info, plan_version.feature_rates.all()))

    @property
    def page_context(self):
        return {
            'plan': self.plan,
            'change_plan_url': reverse(SelectPlanView.urlname, args=[self.domain]),
            'can_purchase_credits': self.can_purchase_credits,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'payment_error_messages': PAYMENT_ERROR_MESSAGES,
            'sms_rate_calc_url': reverse(SMSRatesView.urlname,
                                         args=[self.domain]),
            'user_email': self.request.couch_user.username,
            'show_account_credits': any(
                feature['account_credit'].get('is_visible')
                for feature in self.plan.get('features')
            )
        }


class EditExistingBillingAccountView(DomainAccountingSettings, AsyncHandlerMixin):
    template_name = 'domain/update_billing_contact_info.html'
    urlname = 'domain_update_billing_info'
    page_title = ugettext_lazy("Billing Information")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    @memoized
    def billing_info_form(self):
        is_ops_user = has_privilege(self.request, privileges.ACCOUNTING_ADMIN)
        if self.request.method == 'POST':
            return EditBillingAccountInfoForm(
                self.account, self.domain, self.request.couch_user.username, data=self.request.POST,
                is_ops_user=is_ops_user
            )
        return EditBillingAccountInfoForm(self.account, self.domain, self.request.couch_user.username,
                                          is_ops_user=is_ops_user)

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        if self.account is None:
            raise Http404()
        return super(EditExistingBillingAccountView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'billing_account_info_form': self.billing_info_form,
            'cards': self._get_cards(),
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
        }

    def _get_cards(self):
        if not settings.STRIPE_PRIVATE_KEY:
            return []

        user = self.request.user.username
        payment_method, new_payment_method = StripePaymentMethod.objects.get_or_create(
            web_user=user,
            method_type=PaymentMethodType.STRIPE,
        )
        return payment_method.all_cards_serialized(self.account)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.billing_info_form.is_valid():
            is_saved = self.billing_info_form.save()
            if not is_saved:
                messages.error(
                    request, _("It appears that there was an issue updating your contact information. "
                               "We've been notified of the issue. Please try submitting again, and if the problem "
                               "persists, please try in a few hours."))
            else:
                messages.success(
                    request, _("Billing contact information was successfully updated.")
                )
                return HttpResponseRedirect(reverse(EditExistingBillingAccountView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class DomainBillingStatementsView(DomainAccountingSettings, CRUDPaginatedViewMixin):
    template_name = 'domain/billing_statements.html'
    urlname = 'domain_billing_statements'
    page_title = ugettext_lazy("Billing Statements")

    limit_text = ugettext_lazy("statements per page")
    empty_notification = ugettext_lazy("No Billing Statements match the current criteria.")
    loading_message = ugettext_lazy("Loading statements...")

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def stripe_cards(self):
        return get_customer_cards(self.request.user.username, self.domain)

    @property
    def show_hidden(self):
        if not self.request.user.is_superuser:
            return False
        return bool(self.request.POST.get('additionalData[show_hidden]'))

    @property
    def show_unpaid(self):
        try:
            return json.loads(self.request.POST.get('additionalData[show_unpaid]'))
        except TypeError:
            return False

    @property
    def invoices(self):
        invoices = Invoice.objects.filter(subscription__subscriber__domain=self.domain)
        if not self.show_hidden:
            invoices = invoices.filter(is_hidden=False)
        if self.show_unpaid:
            invoices = invoices.filter(date_paid__exact=None)
        return invoices.order_by('-date_start', '-date_end')

    @property
    def total(self):
        return self.paginated_invoices.count

    @property
    @memoized
    def paginated_invoices(self):
        return Paginator(self.invoices, self.limit)

    @property
    def total_balance(self):
        """
        Returns the total balance of unpaid, unhidden invoices.
        Doesn't take into account the view settings on the page.
        """
        invoices = (Invoice.objects
                    .filter(subscription__subscriber__domain=self.domain)
                    .filter(date_paid__exact=None)
                    .filter(is_hidden=False))
        return invoices.aggregate(
            total_balance=Sum('balance')
        ).get('total_balance') or 0.00

    @property
    def column_names(self):
        return [
            _("Statement No."),
            _("Plan"),
            _("Billing Period"),
            _("Date Due"),
            _("Payment Status"),
            _("PDF"),
        ]

    @property
    def page_context(self):
        pagination_context = self.pagination_context
        pagination_context.update({
            'stripe_options': {
                'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                'stripe_cards': self.stripe_cards,
            },
            'payment_error_messages': PAYMENT_ERROR_MESSAGES,
            'payment_urls': {
                'process_invoice_payment_url': reverse(
                    InvoiceStripePaymentView.urlname,
                    args=[self.domain],
                ),
                'process_bulk_payment_url': reverse(
                    BulkStripePaymentView.urlname,
                    args=[self.domain],
                ),
                'process_wire_invoice_url': reverse(
                    WireInvoiceView.urlname,
                    args=[self.domain],
                ),
            },
            'total_balance': self.total_balance,
        })
        return pagination_context

    @property
    def can_pay_invoices(self):
        return self.request.couch_user.is_domain_admin(self.domain)

    @property
    def paginated_list(self):
        for invoice in self.paginated_invoices.page(self.page).object_list:
            try:
                last_billing_record = BillingRecord.objects.filter(
                    invoice=invoice
                ).latest('date_created')
                if invoice.is_paid:
                    payment_status = (_("Paid on %s.")
                                      % invoice.date_paid.strftime(USER_DATE_FORMAT))
                    payment_class = "label label-default"
                else:
                    payment_status = _("Not Paid")
                    payment_class = "label label-danger"
                date_due = (
                    (invoice.date_due.strftime(USER_DATE_FORMAT)
                     if not invoice.is_paid else _("Already Paid"))
                    if invoice.date_due else _("None")
                )
                yield {
                    'itemData': {
                        'id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'start': invoice.date_start.strftime(USER_DATE_FORMAT),
                        'end': invoice.date_end.strftime(USER_DATE_FORMAT),
                        'plan': invoice.subscription.plan_version.user_facing_description,
                        'payment_status': payment_status,
                        'payment_class': payment_class,
                        'date_due': date_due,
                        'pdfUrl': reverse(
                            BillingStatementPdfView.urlname,
                            args=[self.domain, last_billing_record.pdf_data_id]
                        ),
                        'canMakePayment': (not invoice.is_paid
                                           and self.can_pay_invoices),
                        'balance': "%s" % quantize_accounting_decimal(invoice.balance),
                    },
                    'template': 'statement-row-template',
                }
            except BillingRecord.DoesNotExist:
                log_accounting_error(
                    "An invoice was generated for %(invoice_id)d "
                    "(domain: %(domain)s), but no billing record!" % {
                        'invoice_id': invoice.id,
                        'domain': self.domain,
                    }
                )

    def refresh_item(self, item_id):
        pass

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    def dispatch(self, request, *args, **kwargs):
        if self.account is None:
            raise Http404()
        return super(DomainBillingStatementsView, self).dispatch(request, *args, **kwargs)


class BaseStripePaymentView(DomainAccountingSettings):
    http_method_names = ['post']

    @property
    def account(self):
        raise NotImplementedError("you must implement the property account")

    @property
    @memoized
    def billing_admin(self):
        if self.request.couch_user.can_edit_billing():
            return self.request.couch_user.username
        else:
            raise PaymentRequestError(
                "The logged in user was not a billing admin."
            )

    def get_or_create_payment_method(self):
        return StripePaymentMethod.objects.get_or_create(
            web_user=self.billing_admin,
            method_type=PaymentMethodType.STRIPE,
        )[0]

    def get_payment_handler(self):
        """Returns a StripePaymentHandler object
        """
        raise NotImplementedError("You must implement get_payment_handler()")

    def post(self, request, *args, **kwargs):
        try:
            payment_handler = self.get_payment_handler()
            response = payment_handler.process_request(request)
        except PaymentRequestError as e:
            log_accounting_error(
                "Failed to process Stripe Payment due to bad "
                "request for domain %(domain)s user %(web_user)s: "
                "%(error)s" % {
                    'domain': self.domain,
                    'web_user': self.request.user.username,
                    'error': e,
                }
            )
            response = {
                'error': {
                    'message': _(
                        "There was an issue processing your payment. No "
                        "charges were made. We're looking into the issue "
                        "as quickly as possible. Sorry for the inconvenience."
                    )
                }
            }

        return json_response(response)


class CreditsStripePaymentView(BaseStripePaymentView):
    urlname = 'domain_credits_payment'

    @property
    @memoized
    def account(self):
        return BillingAccount.get_or_create_account_by_domain(
            self.domain,
            created_by=self.request.user.username,
            account_type=BillingAccountType.USER_CREATED,
            entry_point=EntryPoint.SELF_STARTED,
            last_payment_method=LastPayment.CC_ONE_TIME,
        )[0]

    def get_payment_handler(self):
        return CreditStripePaymentHandler(
            self.get_or_create_payment_method(),
            self.domain,
            self.account,
            subscription=Subscription.get_active_subscription_by_domain(self.domain),
            post_data=self.request.POST.copy(),
        )


class CreditsWireInvoiceView(DomainAccountingSettings):
    http_method_names = ['post']
    urlname = 'domain_wire_payment'

    @method_decorator(login_and_domain_required)
    def dispatch(self, request, *args, **kwargs):
        return super(CreditsWireInvoiceView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        emails = request.POST.get('emails', []).split()
        invalid_emails = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                invalid_emails.append(email)
        if invalid_emails:
            message = (_('The following e-mail addresses contain invalid characters, or are missing required '
                         'characters: ') + ', '.join(['"{}"'.format(email) for email in invalid_emails]))
            return json_response({'error': {'message': message}})
        amount = Decimal(request.POST.get('amount', 0))
        wire_invoice_factory = DomainWireInvoiceFactory(request.domain, contact_emails=emails)
        try:
            wire_invoice_factory.create_wire_credits_invoice(self._get_items(request), amount)
        except Exception as e:
            return json_response({'error': {'message': str(e)}})

        return json_response({'success': True})

    @staticmethod
    def _get_items(request):
        if Decimal(request.POST.get('general_credit', 0)) > 0:
            return [{
                'type': 'General Credits',
                'amount': Decimal(request.POST.get('general_credit', 0))
            }]

        return []


class InvoiceStripePaymentView(BaseStripePaymentView):
    urlname = 'domain_invoice_payment'

    @property
    @memoized
    def invoice(self):
        try:
            invoice_id = self.request.POST['invoice_id']
        except IndexError:
            raise PaymentRequestError("invoice_id is required")
        try:
            return Invoice.objects.get(pk=invoice_id)
        except Invoice.DoesNotExist:
            raise PaymentRequestError(
                "Could not find a matching invoice for invoice_id '%s'"
                % invoice_id
            )

    @property
    def account(self):
        return self.invoice.subscription.account

    def get_payment_handler(self):
        return InvoiceStripePaymentHandler(
            self.get_or_create_payment_method(), self.domain, self.invoice
        )


class BulkStripePaymentView(BaseStripePaymentView):
    urlname = 'domain_bulk_payment'

    @property
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    def get_payment_handler(self):
        return BulkStripePaymentHandler(
            self.get_or_create_payment_method(), self.domain
        )


class WireInvoiceView(View):
    http_method_names = ['post']
    urlname = 'domain_wire_invoice'

    @method_decorator(require_permission(Permissions.edit_billing))
    def dispatch(self, request, *args, **kwargs):
        return super(WireInvoiceView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        emails = request.POST.get('emails', []).split()
        balance = Decimal(request.POST.get('customPaymentAmount', 0))
        wire_invoice_factory = DomainWireInvoiceFactory(request.domain, contact_emails=emails)
        try:
            wire_invoice_factory.create_wire_invoice(balance)
        except Exception as e:
            return json_response({'error': {'message', e}})

        return json_response({'success': True})


class BillingStatementPdfView(View):
    urlname = 'domain_billing_statement_download'

    @method_decorator(require_permission(Permissions.edit_billing))
    def dispatch(self, request, *args, **kwargs):
        return super(BillingStatementPdfView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        domain = args[0]
        statement_id = kwargs.get('statement_id')
        if statement_id is None or domain is None:
            raise Http404()
        try:
            invoice_pdf = InvoicePdf.get(statement_id)
        except ResourceNotFound:
            raise Http404()

        try:
            if invoice_pdf.is_wire:
                invoice = WireInvoice.objects.get(
                    pk=invoice_pdf.invoice_id,
                    domain=domain
                )
            else:
                invoice = Invoice.objects.get(
                    pk=invoice_pdf.invoice_id,
                    subscription__subscriber__domain=domain
                )
        except (Invoice.DoesNotExist, WireInvoice.DoesNotExist):
            raise Http404()

        if invoice.is_wire:
            edition = 'Bulk'
        else:
            edition = DESC_BY_EDITION[invoice.subscription.plan_version.plan.edition]['name']
        filename = "%(pdf_id)s_%(domain)s_%(edition)s_%(filename)s" % {
            'pdf_id': invoice_pdf._id,
            'domain': domain,
            'edition': edition,
            'filename': invoice_pdf.get_filename(invoice),
        }
        try:
            data = invoice_pdf.get_data(invoice)
            response = HttpResponse(data, content_type='application/pdf')
            response['Content-Disposition'] = 'inline;filename="%s' % filename
        except Exception as e:
            log_accounting_error('Fetching invoice PDF failed: %s' % e)
            return HttpResponse(_("Could not obtain billing statement. "
                                  "An issue has been submitted."))
        return response


class InternalSubscriptionManagementView(BaseAdminProjectSettingsView):
    template_name = 'domain/internal_subscription_management.html'
    urlname = 'internal_subscription_mgmt'
    page_title = ugettext_lazy("Dimagi Internal Subscription Management")
    form_classes = INTERNAL_SUBSCRIPTION_MANAGEMENT_FORMS

    @method_decorator(require_superuser)
    @use_jquery_ui
    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(InternalSubscriptionManagementView, self).dispatch(request, *args, **kwargs)

    @method_decorator(require_superuser)
    def post(self, request, *args, **kwargs):
        form = self.get_post_form
        if form.is_valid():
            try:
                form.process_subscription_management()
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
            except (NewSubscriptionError, SubscriptionAdjustmentError) as e:
                messages.error(self.request, mark_safe(
                    'This request will require Ops assistance. '
                    'Please explain to <a href="mailto:%(ops_email)s">%(ops_email)s</a>'
                    ' what you\'re trying to do and report the following error: <strong>"%(error)s"</strong>' % {
                        'error': e.message,
                        'ops_email': settings.ACCOUNTS_EMAIL,
                    }
                ))
        return self.get(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'is_form_editable': self.is_form_editable,
            'plan_name': Subscription.get_subscribed_plan_by_domain(self.domain),
            'select_subscription_type_form': self.select_subscription_type_form,
            'subscription_management_forms': list(self.slug_to_form.values()),
            'today': datetime.date.today(),
        }

    @property
    def get_post_form(self):
        return self.slug_to_form[self.request.POST.get('slug')]

    @property
    @memoized
    def slug_to_form(self):
        def create_form(form_class):
            if self.request.method == 'POST' and form_class.slug == self.request.POST.get('slug'):
                return form_class(self.domain, self.request.couch_user.username, self.request.POST)
            return form_class(self.domain, self.request.couch_user.username)
        return {form_class.slug: create_form(form_class) for form_class in self.form_classes}

    @property
    @memoized
    def select_subscription_type_form(self):
        if self.request.method == 'POST' and 'slug' in self.request.POST:
            return SelectSubscriptionTypeForm({
                'subscription_type': self.request.POST['slug'],
            })

        subscription_type = None
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if subscription is None:
            subscription_type = None
        else:
            plan = subscription.plan_version.plan
            if subscription.service_type == SubscriptionType.IMPLEMENTATION:
                subscription_type = ContractedPartnerForm.slug
            elif plan.edition == SoftwarePlanEdition.ENTERPRISE:
                subscription_type = DimagiOnlyEnterpriseForm.slug
            elif plan.edition == SoftwarePlanEdition.ADVANCED:
                subscription_type = AdvancedExtendedTrialForm.slug

        return SelectSubscriptionTypeForm(
            {'subscription_type': subscription_type},
            disable_input=not self.is_form_editable,
        )

    @property
    def is_form_editable(self):
        return not self.slug_to_form[ContractedPartnerForm.slug].is_uneditable


class SelectPlanView(DomainAccountingSettings):
    template_name = 'domain/select_plan.html'
    urlname = 'domain_select_plan'
    page_title = ugettext_lazy("Change Plan")
    step_title = ugettext_lazy("Select Plan")
    edition = None
    lead_text = ugettext_lazy("Please select a plan below that fits your organization's needs.")

    @property
    def edition_name(self):
        if self.edition:
            return DESC_BY_EDITION[self.edition]['name']

    @property
    def parent_pages(self):
        return [
            {
                'title': DomainSubscriptionView.page_title,
                'url': reverse(DomainSubscriptionView.urlname, args=[self.domain]),
            }
        ]

    @property
    def steps(self):
        edition_name = " (%s)" % self.edition_name if self.edition_name else ""
        return [
            {
                'title': _("1. Select a Plan%(edition_name)s") % {
                    "edition_name": edition_name
                },
                'url': reverse(SelectPlanView.urlname, args=[self.domain]),
            }
        ]

    @property
    def main_context(self):
        context = super(SelectPlanView, self).main_context
        context.update({
            'steps': self.steps,
            'step_title': self.step_title,
            'lead_text': self.lead_text,
        })
        return context

    @property
    def page_context(self):
        return {
            'editions': [
                (edition.lower(), DESC_BY_EDITION[edition])
                for edition in [
                    SoftwarePlanEdition.COMMUNITY,
                    SoftwarePlanEdition.STANDARD,
                    SoftwarePlanEdition.PRO,
                    SoftwarePlanEdition.ADVANCED,
                    SoftwarePlanEdition.ENTERPRISE,
                ]
            ],
            'current_edition': (self.current_subscription.plan_version.plan.edition.lower()
                                if self.current_subscription is not None
                                and not self.current_subscription.is_trial
                                else ""),
        }


class EditPrivacySecurityView(BaseAdminProjectSettingsView):
    template_name = "domain/admin/project_privacy.html"
    urlname = "privacy_info"
    page_title = ugettext_lazy("Privacy and Security")

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def privacy_form(self):
        initial = {
            "secure_submissions": self.domain_object.secure_submissions,
            "restrict_superusers": self.domain_object.restrict_superusers,
            "allow_domain_requests": self.domain_object.allow_domain_requests,
            "hipaa_compliant": self.domain_object.hipaa_compliant,
            "secure_sessions": self.domain_object.secure_sessions,
            "two_factor_auth": self.domain_object.two_factor_auth,
            "strong_mobile_passwords": self.domain_object.strong_mobile_passwords,
        }
        if self.request.method == 'POST':
            return PrivacySecurityForm(self.request.POST, initial=initial,
                                       user_name=self.request.couch_user.username,
                                       domain=self.request.domain)
        return PrivacySecurityForm(initial=initial, user_name=self.request.couch_user.username,
                                   domain=self.request.domain)

    @property
    def page_context(self):
        return {
            'privacy_form': self.privacy_form
        }

    def post(self, request, *args, **kwargs):
        if self.privacy_form.is_valid():
            self.privacy_form.save(self.domain_object)
            messages.success(request, _("Your project settings have been saved!"))
        return self.get(request, *args, **kwargs)


class SelectedEnterprisePlanView(SelectPlanView):
    template_name = 'domain/selected_enterprise_plan.html'
    urlname = 'enterprise_request_quote'
    step_title = ugettext_lazy("Contact Dimagi")
    edition = SoftwarePlanEdition.ENTERPRISE

    @property
    def steps(self):
        last_steps = super(SelectedEnterprisePlanView, self).steps
        last_steps.append({
            'title': _("2. Contact Dimagi"),
            'url': reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    @memoized
    def is_not_redirect(self):
        return not 'plan_edition' in self.request.POST

    @property
    @memoized
    def enterprise_contact_form(self):
        if self.request.method == 'POST' and self.is_not_redirect:
            return EnterprisePlanContactForm(self.domain, self.request.couch_user, data=self.request.POST)
        return EnterprisePlanContactForm(self.domain, self.request.couch_user)

    @property
    def page_context(self):
        return {
            'enterprise_contact_form': self.enterprise_contact_form,
        }

    def post(self, request, *args, **kwargs):
        if self.is_not_redirect and self.enterprise_contact_form.is_valid():
            self.enterprise_contact_form.send_message()
            messages.success(request, _("Your request was sent to Dimagi. "
                                        "We will try our best to follow up in a timely manner."))
            return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class ConfirmSelectedPlanView(SelectPlanView):
    template_name = 'domain/confirm_plan.html'
    urlname = 'confirm_selected_plan'
    step_title = ugettext_lazy("Confirm Plan")

    @property
    def steps(self):
        last_steps = super(ConfirmSelectedPlanView, self).steps
        last_steps.append({
            'title': _("2. Confirm Plan"),
            'url': reverse(SelectPlanView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    @memoized
    def edition(self):
        edition = self.request.POST.get('plan_edition').title()
        if edition not in [e[0] for e in SoftwarePlanEdition.CHOICES]:
            raise Http404()
        return edition

    @property
    @memoized
    def selected_plan_version(self):
        return DefaultProductPlan.get_default_plan_version(self.edition)

    @property
    def downgrade_messages(self):
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        downgrades = get_change_status(
            subscription.plan_version if subscription else None,
            self.selected_plan_version
        )[1]
        downgrade_handler = DomainDowngradeStatusHandler(
            self.domain_object, self.selected_plan_version, downgrades,
        )
        return downgrade_handler.get_response()

    @property
    def page_context(self):
        return {
            'downgrade_messages': self.downgrade_messages,
            'current_plan': (self.current_subscription.plan_version.user_facing_description
                             if self.current_subscription is not None else None),
            'show_community_notice': (self.edition == SoftwarePlanEdition.COMMUNITY
                                      and self.current_subscription is None),
        }

    @property
    def main_context(self):
        context = super(ConfirmSelectedPlanView, self).main_context
        context.update({
            'plan': self.selected_plan_version.user_facing_description,
        })
        return context

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse(SelectPlanView.urlname, args=[self.domain]))

    def post(self, request, *args, **kwargs):
        if self.edition == SoftwarePlanEdition.ENTERPRISE:
            return HttpResponseRedirect(reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]))
        return super(ConfirmSelectedPlanView, self).get(request, *args, **kwargs)


class ConfirmBillingAccountInfoView(ConfirmSelectedPlanView, AsyncHandlerMixin):
    template_name = 'domain/confirm_billing_info.html'
    urlname = 'confirm_billing_account_info'
    step_title = ugettext_lazy("Confirm Billing Information")
    is_new = False
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(ConfirmBillingAccountInfoView, self).dispatch(request, *args, **kwargs)

    @property
    def steps(self):
        last_steps = super(ConfirmBillingAccountInfoView, self).steps
        last_steps.append({
            'title': _("3. Confirm Billing Account"),
            'url': reverse(ConfirmBillingAccountInfoView.urlname, args=[self.domain]),
        })
        return last_steps

    @property
    @memoized
    def account(self):
        if self.current_subscription:
            return self.current_subscription.account
        account, self.is_new = BillingAccount.get_or_create_account_by_domain(
            self.domain,
            created_by=self.request.couch_user.username,
            account_type=BillingAccountType.USER_CREATED,
            entry_point=EntryPoint.SELF_STARTED,
        )
        return account

    @property
    def payment_method(self):
        user = self.request.user.username
        payment_method, __ = StripePaymentMethod.objects.get_or_create(
            web_user=user,
            method_type=PaymentMethodType.STRIPE,
        )
        return payment_method

    @property
    @memoized
    def is_form_post(self):
        return 'company_name' in self.request.POST

    @property
    @memoized
    def billing_account_info_form(self):
        if self.request.method == 'POST' and self.is_form_post:
            return ConfirmNewSubscriptionForm(
                self.account, self.domain, self.request.couch_user.username,
                self.selected_plan_version, self.current_subscription, data=self.request.POST
            )
        return ConfirmNewSubscriptionForm(self.account, self.domain, self.request.couch_user.username,
                                          self.selected_plan_version, self.current_subscription)

    @property
    def page_context(self):
        return {
            'billing_account_info_form': self.billing_account_info_form,
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'cards': self.payment_method.all_cards_serialized(self.account)
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.is_form_post and self.billing_account_info_form.is_valid():
            is_saved = self.billing_account_info_form.save()
            software_plan_name = DESC_BY_EDITION[self.selected_plan_version.plan.edition]['name']
            if not is_saved:
                messages.error(
                    request, _(
                        "It appears there was an issue subscribing your project to the %s Software Plan. You "
                        "may try resubmitting, but if that doesn't work, rest assured someone will be "
                        "contacting you shortly."
                    ) % software_plan_name
                )
            else:
                messages.success(
                    request, _(
                        "Your project has been successfully subscribed to the %s Software Plan."
                    ) % software_plan_name
                )
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
        return super(ConfirmBillingAccountInfoView, self).post(request, *args, **kwargs)


class SubscriptionMixin(object):

    @property
    @memoized
    def subscription(self):
        subscription = Subscription.get_active_subscription_by_domain(self.domain)
        if subscription is None:
            raise Http404
        if subscription.is_renewed:
            raise Http404
        return subscription


class SubscriptionRenewalView(SelectPlanView, SubscriptionMixin):
    urlname = "domain_subscription_renewal"
    page_title = ugettext_lazy("Renew Plan")
    step_title = ugettext_lazy("Renew or Change Plan")

    @property
    def lead_text(self):
        return ugettext_lazy("Based on your current usage we recommend you use the <strong>{plan}</strong> plan"
                             .format(plan=self.current_subscription.plan_version.plan.edition))

    @property
    def main_context(self):
        context = super(SubscriptionRenewalView, self).main_context
        context.update({'is_renewal': True})
        return context

    @property
    def page_context(self):
        context = super(SubscriptionRenewalView, self).page_context

        current_privs = get_privileges(self.subscription.plan_version)
        plan = DefaultProductPlan.get_lowest_edition(
            current_privs, return_plan=False,
        ).lower()

        context['current_edition'] = (plan
                                      if self.current_subscription is not None
                                      and not self.current_subscription.is_trial
                                      else "")
        return context


class ConfirmSubscriptionRenewalView(DomainAccountingSettings, AsyncHandlerMixin, SubscriptionMixin):
    template_name = 'domain/confirm_subscription_renewal.html'
    urlname = 'domain_subscription_renewal_confirmation'
    page_title = ugettext_lazy("Renew Plan")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @method_decorator(require_POST)
    def dispatch(self, request, *args, **kwargs):
        return super(ConfirmSubscriptionRenewalView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def next_plan_version(self):
        plan_version = DefaultProductPlan.get_default_plan_version(self.new_edition)
        if plan_version is None:
            log_accounting_error(
                "Could not find a matching renewable plan "
                "for %(domain)s, subscription number %(sub_pk)s." % {
                    'domain': self.domain,
                    'sub_pk': self.subscription.pk
                }
            )
            raise Http404
        return plan_version

    @property
    @memoized
    def confirm_form(self):
        if self.request.method == 'POST' and "from_plan_page" not in self.request.POST:
            return ConfirmSubscriptionRenewalForm(
                self.account, self.domain, self.request.couch_user.username,
                self.subscription, self.next_plan_version,
                data=self.request.POST,
            )
        return ConfirmSubscriptionRenewalForm(
            self.account, self.domain, self.request.couch_user.username,
            self.subscription, self.next_plan_version,
        )

    @property
    def page_context(self):
        return {
            'subscription': self.subscription,
            'plan': self.subscription.plan_version.user_facing_description,
            'confirm_form': self.confirm_form,
            'next_plan': self.next_plan_version.user_facing_description,
        }

    @property
    def new_edition(self):
        return self.request.POST.get('plan_edition').title()

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.new_edition == SoftwarePlanEdition.ENTERPRISE:
            return HttpResponseRedirect(reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]))
        if self.confirm_form.is_valid():
            is_saved = self.confirm_form.save()
            if not is_saved:
                messages.error(
                    request, _(
                        "There was an issue renewing your subscription. We "
                        "have been notified of the issue. Please try "
                        "submitting again, and if the problem persists, "
                        "please try in a few hours."
                    )
                )
            else:
                messages.success(
                    request, _("Your subscription was successfully renewed!")
                )
                return HttpResponseRedirect(
                    reverse(DomainSubscriptionView.urlname, args=[self.domain])
                )
        return self.get(request, *args, **kwargs)


class EmailOnDowngradeView(View):
    urlname = "email_on_downgrade"

    def post(self, request, *args, **kwargs):
        message = '\n'.join([
            '{user} is downgrading the subscription for {domain} from {old_plan} to {new_plan}.',
            '',
            'Note from user: {note}',
        ]).format(
            user=request.couch_user.username,
            domain=request.domain,
            old_plan=request.POST.get('old_plan', 'unknown'),
            new_plan=request.POST.get('new_plan', 'unknown'),
            note=request.POST.get('note', 'none'),
        )

        send_mail_async.delay(
            '{}Subscription downgrade for {}'.format(
                '[staging] ' if settings.SERVER_ENVIRONMENT == "staging" else "",
                request.domain
            ), message, settings.DEFAULT_FROM_EMAIL, [settings.GROWTH_EMAIL]
        )
        return json_response({'success': True})


class ExchangeSnapshotsView(BaseAdminProjectSettingsView):
    template_name = 'domain/snapshot_settings.html'
    urlname = 'domain_snapshot_settings'
    page_title = ugettext_lazy("CommCare Exchange")

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'snapshots': list(self.domain_object.snapshots()),
            'published_snapshot': self.domain_object.published_snapshot(),
        }


class CreateNewExchangeSnapshotView(BaseAdminProjectSettingsView):
    template_name = 'domain/create_snapshot.html'
    urlname = 'domain_create_snapshot'
    page_title = ugettext_lazy("Publish New Version")
    strict_domain_fetching = True

    @method_decorator(domain_admin_required)
    @use_jquery_ui
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def parent_pages(self):
        return [{
            'title': ExchangeSnapshotsView.page_title,
            'url': reverse(ExchangeSnapshotsView.urlname, args=[self.domain]),
        }]

    @property
    def page_context(self):
        app_forms = self.app_forms
        fixture_forms = self.fixture_forms
        context = {
            'form': self.snapshot_settings_form,
            'app_forms': app_forms,
            'app_ids': [app.id for app, form in app_forms],
            'fixture_forms': fixture_forms,
            'fixture_ids': [data.id for data, form in fixture_forms],
            'can_publish_as_org': self.can_publish_as_org,
            'autocomplete_fields': ('project_type', 'phone_model', 'user_type', 'city', 'countries', 'region'),
        }
        if self.published_snapshot:
            context.update({
                'published_as_org': self.published_snapshot.publisher == 'organization',
                'author': self.published_snapshot.author,
            })
        elif self.request.method == 'POST':
            context.update({
                'published_as_org': self.request.POST.get('publisher', '') == 'organization',
                'author': self.request.POST.get('author', '')
            })
        return context

    @property
    def can_publish_as_org(self):
        return False

    @property
    @memoized
    def snapshots(self):
        return list(self.domain_object.snapshots())

    @property
    @memoized
    def published_snapshot(self):
        return self.snapshots[0] if self.snapshots else self.domain_object

    @property
    @memoized
    def published_apps(self):
        published_apps = {}
        if self.published_snapshot:
            for app in self.published_snapshot.full_applications():
                base_app_id = app.copy_of if self.domain_object == self.published_snapshot else app.copied_from.copy_of
                if base_app_id:
                    published_apps[base_app_id] = app
        return published_apps

    @property
    def app_forms(self):
        app_forms = []
        for app in self.domain_object.applications():
            if self.request.method == 'POST':
                app_forms.append((app, SnapshotApplicationForm(self.request.POST, prefix=app.id)))
            elif self.published_snapshot and app.copy_of in self.published_apps:
                original = self.published_apps[app.copy_of]
                app_forms.append((app, SnapshotApplicationForm(initial={
                    'publish': True,
                    'name': original.name,
                    'description': original.description,
                    'deployment_date': original.deployment_date,
                    'user_type': original.user_type,
                    'attribution_notes': original.attribution_notes,
                    'phone_model': original.phone_model,

                }, prefix=app.id)))
            else:
                app_forms.append((app,
                                  SnapshotApplicationForm(
                                      initial={
                                          'publish': (self.published_snapshot is None
                                                      or self.published_snapshot == self.domain_object)
                                      }, prefix=app.id)))
        return app_forms

    @property
    @memoized
    def published_fixtures(self):
        return [f.copy_from for f in FixtureDataType.by_domain(self.published_snapshot._id)]

    @property
    def fixture_forms(self):
        fixture_forms = []
        for fixture in FixtureDataType.by_domain(self.domain_object.name):
            fixture.id = fixture._id
            if self.request.method == 'POST':
                fixture_forms.append((fixture,
                    SnapshotFixtureForm(self.request.POST, prefix=fixture._id)))
            else:
                fixture_forms.append((fixture,
                                  SnapshotFixtureForm(
                                      initial={
                                          'publish': (self.published_snapshot == self.domain_object
                                                      or fixture._id in self.published_fixtures)
                                      }, prefix=fixture._id)))

        return fixture_forms

    @property
    @memoized
    def snapshot_settings_form(self):
        if self.request.method == 'POST':
            form = SnapshotSettingsForm(self.request.POST,
                                        self.request.FILES,
                                        domain=self.domain_object,
                                        is_superuser=self.request.user.is_superuser)
            return form

        proj = self.published_snapshot if self.published_snapshot else self.domain_object
        initial = {
            'case_sharing': json.dumps(proj.case_sharing),
            'publish_on_submit': True,
            'share_multimedia': self.published_snapshot.multimedia_included if self.published_snapshot else True,
        }
        init_attribs = ['default_timezone', 'project_type', 'license']
        if self.published_snapshot:
            init_attribs.extend(['title', 'description', 'short_description'])
            if self.published_snapshot.yt_id:
                initial['video'] = 'http://www.youtube.com/watch?v=%s' % self.published_snapshot.yt_id
        for attr in init_attribs:
            initial[attr] = getattr(proj, attr)

        return SnapshotSettingsForm(initial=initial,
                                    domain=self.domain_object,
                                    is_superuser=self.request.user.is_superuser)

    @property
    @memoized
    def has_published_apps(self):
        for app in self.domain_object.applications():
            if self.request.POST.get("%s-publish" % app.id, False):
                return True
        messages.error(self.request, _("Cannot publish a project without applications to CommCare Exchange"))
        return False

    @property
    def has_signed_eula(self):
        eula_signed = self.request.couch_user.is_eula_signed()
        if not eula_signed:
            messages.error(self.request, _("You must agree to our eula to publish a project to Exchange"))
        return eula_signed

    @property
    def has_valid_form(self):
        is_valid = self.snapshot_settings_form.is_valid()
        if not is_valid:
            messages.error(self.request, _("There are some problems with your form. "
                                           "Please address these issues and try again."))
        return is_valid

    def post(self, request, *args, **kwargs):
        if self.has_published_apps and self.has_signed_eula and self.has_valid_form:
            new_license = request.POST['license']
            if request.POST.get('share_multimedia', False):
                app_ids = self.snapshot_settings_form._get_apps_to_publish()
                media = self.domain_object.all_media(from_apps=app_ids)
                for m_file in media:
                    if self.domain not in m_file.shared_by:
                        m_file.shared_by.append(self.domain)

                    # set the license of every multimedia file that doesn't yet have a license set
                    if not m_file.license:
                        m_file.update_or_add_license(self.domain, type=new_license, should_save=False)

                    m_file.save()

            if not request.POST.get('share_reminders', False):
                share_reminders = False
            else:
                share_reminders = True

            copy_by_id = set()
            for k in request.POST:
                if k.endswith("-publish"):
                    copy_by_id.add(k[:-len("-publish")])

            old = self.domain_object.published_snapshot()
            new_domain = self.domain_object.save_snapshot(
                share_reminders=share_reminders, copy_by_id=copy_by_id)
            new_domain.license = new_license
            new_domain.description = request.POST['description']
            new_domain.short_description = request.POST['short_description']
            new_domain.project_type = request.POST['project_type']
            new_domain.title = request.POST['title']
            new_domain.multimedia_included = request.POST.get('share_multimedia', '') == 'on'
            new_domain.publisher = request.POST.get('publisher', None) or 'user'
            if request.POST.get('video'):
                new_domain.yt_id = self.snapshot_settings_form.cleaned_data['video']

            new_domain.author = request.POST.get('author', None)

            new_domain.is_approved = False
            new_domain.is_starter_app = request.POST.get('is_starter_app', '') == 'on'
            publish_on_submit = request.POST.get('publish_on_submit', "no") == "yes"

            image = self.snapshot_settings_form.cleaned_data['image']
            if image:
                new_domain.image_path = image.name
                new_domain.image_type = image.content_type
            elif request.POST.get('old_image', False):
                new_domain.image_path = old.image_path
                new_domain.image_type = old.image_type

            documentation_file = self.snapshot_settings_form.cleaned_data['documentation_file']
            if documentation_file:
                new_domain.documentation_file_path = documentation_file.name
                new_domain.documentation_file_type = documentation_file.content_type
            elif request.POST.get('old_documentation_file', False):
                new_domain.documentation_file_path = old.documentation_file_path
                new_domain.documentation_file_type = old.documentation_file_type

            if publish_on_submit:
                new_domain.save()
                _publish_snapshot(request, self.domain_object, published_snapshot=new_domain)
            else:
                new_domain.published = False
                new_domain.save()

            if image:
                im = Image.open(image)
                out = io.BytesIO()
                im.thumbnail((200, 200), Image.ANTIALIAS)
                im.save(out, new_domain.image_type.split('/')[-1])
                new_domain.put_attachment(content=out.getvalue(), name=image.name)
            elif request.POST.get('old_image', False):
                new_domain.put_attachment(content=old.fetch_attachment(old.image_path), name=new_domain.image_path)

            if documentation_file:
                new_domain.put_attachment(content=documentation_file, name=documentation_file.name)
            elif request.POST.get('old_documentation_file', False):
                new_domain.put_attachment(content=old.fetch_attachment(old.documentation_file_path),
                                          name=new_domain.documentation_file_path)

            for application in new_domain.full_applications():
                # Note that application is a build. If the original app has a build then application.copied_from
                # will be a build and application.copied_from.copy_of will be the original app ID, otherwise
                # application.copied_from will be the original app. (FB 190587) See also self.published_apps()
                original_id = application.copied_from.copy_of if application.copied_from.copy_of \
                    else application.copied_from._id
                name_field = "%s-name" % original_id
                if name_field not in request.POST:
                    continue

                application.name = request.POST[name_field]
                application.description = request.POST["%s-description" % original_id]
                date_picked = request.POST["%s-deployment_date" % original_id]
                try:
                    date_picked = dateutil.parser.parse(date_picked)
                    if date_picked.year > 2009:
                        application.deployment_date = date_picked
                except Exception:
                    pass
                application.phone_model = request.POST["%s-phone_model" % original_id]
                application.attribution_notes = request.POST["%s-attribution_notes" % original_id]
                application.user_type = request.POST["%s-user_type" % original_id]

                if not new_domain.multimedia_included:
                    application.multimedia_map = {}
                application.save()

            for fixture in FixtureDataType.by_domain(new_domain.name):
                old_id = FixtureDataType.by_domain_tag(self.domain_object.name,
                                                       fixture.tag).first()._id
                fixture.description = request.POST["%s-description" % old_id]
                fixture.save()

            messages.success(request, (_("Created a new version of your app. This version will be posted to "
                                         "CommCare Exchange pending approval by admins.") if publish_on_submit
                                       else _("Created a new version of your app.")))
            return redirect(ExchangeSnapshotsView.urlname, self.domain)
        return self.get(request, *args, **kwargs)


class ManageProjectMediaView(BaseAdminProjectSettingsView):
    urlname = 'domain_manage_multimedia'
    page_title = ugettext_lazy("Multimedia Sharing")
    template_name = 'domain/admin/media_manager.html'

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def project_media_data(self):
        return [{
            'license': m.license.type if m.license else 'public',
            'shared': self.domain in m.shared_by,
            'url': m.url(),
            'm_id': m._id,
            'tags': m.tags.get(self.domain, []),
            'type': m.doc_type,
        } for m in self.request.project.all_media()]

    @property
    def page_context(self):
        return {
            'media': self.project_media_data,
            'licenses': list(LICENSES.items()),
        }

    @retry_resource(3)
    def post(self, request, *args, **kwargs):
        for m_file in request.project.all_media():
            if '%s_tags' % m_file._id in request.POST:
                m_file.tags[self.domain] = request.POST.get('%s_tags' % m_file._id, '').split(' ')

            if self.domain not in m_file.shared_by and request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.append(self.domain)
            elif self.domain in m_file.shared_by and not request.POST.get('%s_shared' % m_file._id, False):
                m_file.shared_by.remove(self.domain)

            if '%s_license' % m_file._id in request.POST:
                m_file.update_or_add_license(self.domain,
                                             type=request.POST.get('%s_license' % m_file._id, 'public'),
                                             should_save=True)
            m_file.save()
        messages.success(request, _("Multimedia updated successfully!"))
        return self.get(request, *args, **kwargs)


class CaseSearchConfigView(BaseAdminProjectSettingsView):
    urlname = 'case_search_config'
    page_title = ugettext_lazy('Case Search')
    template_name = 'domain/admin/case_search.html'

    @method_decorator(domain_admin_required)
    @method_decorator(toggles.SYNC_SEARCH_CASE_CLAIM.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(CaseSearchConfigView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        request_json = json.loads(request.body)
        enable = request_json.get('enable')
        fuzzies_by_casetype = request_json.get('fuzzy_properties')
        updated_fuzzies = []
        for case_type, properties in six.iteritems(fuzzies_by_casetype):
            fp, created = FuzzyProperties.objects.get_or_create(
                domain=self.domain,
                case_type=case_type
            )
            fp.properties = properties
            fp.save()
            updated_fuzzies.append(fp)

        unneeded_fuzzies = FuzzyProperties.objects.filter(domain=self.domain).exclude(
            case_type__in=list(fuzzies_by_casetype)
        )
        unneeded_fuzzies.delete()

        ignore_patterns = request_json.get('ignore_patterns')
        updated_ignore_patterns = []
        update_ignore_pattern_ids = []
        for ignore_pattern_regex in ignore_patterns:
            rc, created = IgnorePatterns.objects.get_or_create(
                domain=self.domain,
                case_type=ignore_pattern_regex.get('case_type'),
                case_property=ignore_pattern_regex.get('case_property'),
                regex=ignore_pattern_regex.get('regex')
            )
            updated_ignore_patterns.append(rc)
            update_ignore_pattern_ids.append(rc.pk)

        unneeded_ignore_patterns = IgnorePatterns.objects.filter(domain=self.domain).exclude(
            pk__in=update_ignore_pattern_ids
        )
        unneeded_ignore_patterns.delete()

        if enable:
            enable_case_search(self.domain)
        else:
            disable_case_search(self.domain)

        CaseSearchConfig.objects.update_or_create(domain=self.domain, defaults={
            'enabled': request_json.get('enable'),
            'fuzzy_properties': updated_fuzzies,
            'ignore_patterns': updated_ignore_patterns,
        })
        return json_response(self.page_context)

    @property
    def page_context(self):
        apps = get_apps_in_domain(self.domain, include_remote=False)
        case_types = {t for app in apps for t in app.get_case_types() if t}
        current_values = CaseSearchConfig.objects.get_or_none(pk=self.domain)
        return {
            'case_types': sorted(list(case_types)),
            'values': {
                'enabled': current_values.enabled if current_values else False,
                'fuzzy_properties': {
                    fp.case_type: fp.properties for fp in current_values.fuzzy_properties.all()
                } if current_values else {},
                'ignore_patterns': [{
                    'case_type': rc.case_type,
                    'case_property': rc.case_property,
                    'regex': rc.regex
                } for rc in current_values.ignore_patterns.all()] if current_values else {}
            }
        }


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


class BaseInternalDomainSettingsView(BaseProjectSettingsView):
    strict_domain_fetching = True

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(BaseInternalDomainSettingsView, self).main_context
        context.update({
            'project': self.domain_object,
        })
        return context

    @property
    def page_name(self):
        return mark_safe("%s <small>Internal</small>" % self.page_title)


class EditInternalDomainInfoView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_settings'
    page_title = ugettext_lazy("Project Information")
    template_name = 'domain/internal_settings.html'
    strict_domain_fetching = True

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    @use_jquery_ui  # datepicker
    @use_multiselect
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def autocomplete_fields(self):
        return ['countries']

    @property
    @memoized
    def internal_settings_form(self):
        can_edit_eula = CAN_EDIT_EULA.enabled(self.request.couch_user.username)
        if self.request.method == 'POST':
            return DomainInternalForm(self.request.domain, can_edit_eula, self.request.POST)
        initial = {
            'countries': self.domain_object.deployment.countries,
            'is_test': self.domain_object.is_test,
            'use_custom_auto_case_update_limit': 'Y' if self.domain_object.auto_case_update_limit else 'N',
            'auto_case_update_limit': self.domain_object.auto_case_update_limit,
        }
        internal_attrs = [
            'sf_contract_id',
            'sf_account_id',
            'initiative',
            'self_started',
            'area',
            'sub_area',
            'organization_name',
            'notes',
            'phone_model',
            'commtrack_domain',
            'performance_threshold',
            'experienced_threshold',
            'amplifies_workers',
            'amplifies_project',
            'data_access_threshold',
            'business_unit',
            'workshop_region',
            'partner_technical_competency',
            'support_prioritization',
            'gs_continued_involvement',
            'technical_complexity',
            'app_design_comments',
            'training_materials',
            'partner_comments',
            'partner_contact',
            'dimagi_contact',
        ]
        if can_edit_eula:
            internal_attrs += [
                'custom_eula',
                'can_use_data',
            ]
        for attr in internal_attrs:
            val = getattr(self.domain_object.internal, attr)
            if isinstance(val, bool):
                val = 'true' if val else 'false'
            initial[attr] = val
        return DomainInternalForm(self.request.domain, can_edit_eula, initial=initial)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'form': self.internal_settings_form,
            'areas': dict([(a["name"], a["sub_areas"]) for a in settings.INTERNAL_DATA["area"]]),
        }

    def send_handoff_email(self):
        partner_contact = self.internal_settings_form.cleaned_data['partner_contact']
        dimagi_contact = self.internal_settings_form.cleaned_data['dimagi_contact']
        recipients = [partner_contact, dimagi_contact]
        params = {'contact_name': CouchUser.get_by_username(dimagi_contact).human_friendly_name}
        send_html_email_async.delay(
            subject="Project Support Transition",
            recipient=recipients,
            html_content=render_to_string(
                "domain/email/support_handoff.html", params),
            text_content=render_to_string(
                "domain/email/support_handoff.txt", params),
            email_from=settings.SUPPORT_EMAIL,
        )
        messages.success(self.request,
                         _("Sent hand-off email to {}.").format(" and ".join(recipients)))

    def post(self, request, *args, **kwargs):
        if self.internal_settings_form.is_valid():
            old_attrs = copy.copy(self.domain_object.internal)
            self.internal_settings_form.save(self.domain_object)
            eula_props_changed = (bool(old_attrs.custom_eula) != bool(self.domain_object.internal.custom_eula) or
                                  bool(old_attrs.can_use_data) != bool(self.domain_object.internal.can_use_data))

            if eula_props_changed and settings.EULA_CHANGE_EMAIL:
                message = '\n'.join([
                    '{user} changed either the EULA or data sharing properties for domain {domain}.',
                    '',
                    'The properties changed were:',
                    '- Custom eula: {eula_old} --> {eula_new}',
                    '- Can use data: {can_use_data_old} --> {can_use_data_new}'
                ]).format(
                    user=self.request.couch_user.username,
                    domain=self.domain,
                    eula_old=old_attrs.custom_eula,
                    eula_new=self.domain_object.internal.custom_eula,
                    can_use_data_old=old_attrs.can_use_data,
                    can_use_data_new=self.domain_object.internal.can_use_data,
                )
                send_mail_async.delay(
                    'Custom EULA or data use flags changed for {}'.format(self.domain),
                    message, settings.DEFAULT_FROM_EMAIL, [settings.EULA_CHANGE_EMAIL]
                )

            messages.success(request, _("The internal information for project %s was successfully updated!")
                                      % self.domain)
            if self.internal_settings_form.cleaned_data['send_handoff_email']:
                self.send_handoff_email()
            return redirect(self.urlname, self.domain)
        else:
            messages.error(request, _(
                "Your settings are not valid, see below for errors. Correct them and try again!"))
            return self.get(request, *args, **kwargs)


class EditInternalCalculationsView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_calculations'
    page_title = ugettext_lazy("Calculated Properties")
    template_name = 'domain/internal_calculations.html'

    @method_decorator(login_and_domain_required)
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseInternalDomainSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'calcs': CALCS,
            'order': CALC_ORDER,
        }


@login_and_domain_required
@require_superuser
@require_GET
def toggle_diff(request, domain):
    params = json_request(request.GET)
    other_domain = params.get('domain')
    diff = []
    if Domain.get_by_name(other_domain):
        diff = [{'slug': t.slug, 'label': t.label, 'url': reverse(ToggleEditView.urlname, args=[t.slug])}
                for t in feature_previews.all_previews() + all_toggles()
                if t.enabled(request.domain, NAMESPACE_DOMAIN) and not t.enabled(other_domain, NAMESPACE_DOMAIN)]
        diff.sort(cmp=lambda x, y: cmp(x['label'], y['label']))
    return json_response(diff)


@login_and_domain_required
@require_superuser
def calculated_properties(request, domain):
    calc_tag = request.GET.get("calc_tag", '').split('--')
    extra_arg = calc_tag[1] if len(calc_tag) > 1 else ''
    calc_tag = calc_tag[0]

    if not calc_tag or calc_tag not in list(CALC_FNS):
        data = {"error": 'This tag does not exist'}
    else:
        data = {"value": dom_calc(calc_tag, domain, extra_arg)}
    return json_response(data)


def _publish_snapshot(request, domain, published_snapshot=None):
    snapshots = domain.snapshots()
    for snapshot in snapshots:
        if snapshot.published:
            snapshot.published = False
            if not published_snapshot or snapshot.name != published_snapshot.name:
                snapshot.save()
    if published_snapshot:
        if published_snapshot.copied_from.name != domain.name:
            messages.error(request, "Invalid snapshot")
            return False

        # cda stuff. In order to publish a snapshot, a user must have agreed to this
        published_snapshot.cda.signed = True
        published_snapshot.cda.date = datetime.datetime.utcnow()
        published_snapshot.cda.type = 'Content Distribution Agreement'
        if request.couch_user:
            published_snapshot.cda.user_id = request.couch_user.get_id
        published_snapshot.cda.user_ip = get_ip(request)

        published_snapshot.published = True
        published_snapshot.save()
        _notification_email_on_publish(domain, published_snapshot, request.couch_user)
    return True


def _notification_email_on_publish(domain, snapshot, published_by):
    params = {"domain": domain, "snapshot": snapshot,
              "published_by": published_by, "url_base": get_site_domain()}
    text_content = render_to_string(
        "domain/email/published_app_notification.txt", params)
    html_content = render_to_string(
        "domain/email/published_app_notification.html", params)
    recipients = settings.EXCHANGE_NOTIFICATION_RECIPIENTS
    subject = "New App on Exchange: %s" % snapshot.title
    try:
        for recipient in recipients:
            send_html_email_async.delay(subject, recipient, html_content,
                                        text_content=text_content,
                                        email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, "
                        "but the message was:\n%s" % text_content)


@domain_admin_required
def set_published_snapshot(request, domain, snapshot_name=''):
    domain = request.project
    snapshots = domain.snapshots()
    if request.method == 'POST':
        if snapshot_name != '':
            published_snapshot = Domain.get_by_name(snapshot_name)
            _publish_snapshot(request, domain, published_snapshot=published_snapshot)
        else:
            _publish_snapshot(request, domain)
    return redirect('domain_snapshot_settings', domain.name)


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


class FeaturePreviewsView(BaseAdminProjectSettingsView):
    urlname = 'feature_previews'
    page_title = ugettext_lazy("Feature Previews")
    template_name = 'domain/admin/feature_previews.html'

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProjectSettingsView, self).dispatch(request, *args, **kwargs)

    @memoized
    def features(self):
        features = []
        for preview_name in dir(feature_previews):
            if not preview_name.startswith('__'):
                preview = getattr(feature_previews, preview_name)
                if isinstance(preview, feature_previews.FeaturePreview) and preview.has_privilege(self.request):
                    features.append((preview, preview.enabled(self.domain)))

        return sorted(features, key=lambda feature: feature[0].label)

    def get_toggle(self, slug):
        if not slug in [f.slug for f, _ in self.features()]:
            raise Http404()
        try:
            return Toggle.get(slug)
        except ResourceNotFound:
            return Toggle(slug=slug)

    @property
    def page_context(self):
        exclude_previews = ['advanced_itemsets', 'calc_xpaths', 'conditional_enum', 'enum_image']
        return {
            'features': [f for f in self.features() if f[0].slug not in exclude_previews],
        }

    def post(self, request, *args, **kwargs):
        for feature, enabled in self.features():
            self.update_feature(feature, enabled, feature.slug in request.POST)
        feature_previews.previews_dict.clear(self.domain)

        return redirect('feature_previews', domain=self.domain)

    def update_feature(self, feature, current_state, new_state):
        if current_state != new_state:
            toggle_js_domain_cachebuster.clear(self.domain)
            feature.set(self.domain, new_state, NAMESPACE_DOMAIN)
            if feature.save_fn is not None:
                feature.save_fn(self.domain, new_state)


class FlagsAndPrivilegesView(BaseAdminProjectSettingsView):
    urlname = 'feature_flags_and_privileges'
    page_title = ugettext_lazy("Feature Flags and Privileges")
    template_name = 'domain/admin/flags_and_privileges.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(FlagsAndPrivilegesView, self).dispatch(request, *args, **kwargs)

    @memoized
    def enabled_flags(self):
        def _sort_key(toggle_enabled_tuple):
            return (not toggle_enabled_tuple[1], not toggle_enabled_tuple[2], toggle_enabled_tuple[0].label)
        unsorted_toggles = [(
            toggle,
            toggle.enabled(self.domain, namespace=NAMESPACE_DOMAIN),
            toggle.enabled(self.request.couch_user.username, namespace=NAMESPACE_USER)
        ) for toggle in all_toggles()]
        return sorted(unsorted_toggles, key=_sort_key)

    def _get_privileges(self):
        return sorted([
            (privileges.Titles.get_name_from_privilege(privilege),
             domain_has_privilege(self.domain, privilege))
            for privilege in privileges.MAX_PRIVILEGES
        ], key=lambda name_has: (not name_has[1], name_has[0]))

    @property
    def page_context(self):
        return {
            'flags': self.enabled_flags(),
            'use_sql_backend': self.domain_object.use_sql_backend,
            'privileges': self._get_privileges(),
        }


class TransferDomainView(BaseAdminProjectSettingsView):
    urlname = 'transfer_domain_view'
    page_title = ugettext_lazy("Transfer Project")
    template_name = 'domain/admin/transfer_domain.html'

    @property
    @memoized
    def active_transfer(self):
        return TransferDomainRequest.get_active_transfer(self.domain,
                                                         self.request.user.username)

    @property
    @memoized
    def transfer_domain_form(self):
        return TransferDomainForm(self.domain,
                                  self.request.user.username,
                                  self.request.POST or None)

    def get(self, request, *args, **kwargs):

        if self.active_transfer:
            self.template_name = 'domain/admin/transfer_domain_pending.html'

            if request.GET.get('resend', None):
                self.active_transfer.send_transfer_request()
                messages.info(request,
                              _("Resent transfer request for project '{domain}'").format(domain=self.domain))

        return super(TransferDomainView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.transfer_domain_form
        if form.is_valid():
            # Initiate domain transfer
            transfer = form.save()
            transfer.send_transfer_request()
            return HttpResponseRedirect(self.page_url)

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)

    @property
    def page_context(self):
        if self.active_transfer:
            return {'transfer': self.active_transfer.as_dict()}
        else:
            return {'form': self.transfer_domain_form}

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        if not TRANSFER_DOMAIN.enabled(request.domain):
            raise Http404()
        return super(TransferDomainView, self).dispatch(request, *args, **kwargs)


class ActivateTransferDomainView(BasePageView):
    urlname = 'activate_transfer_domain'
    page_title = 'Activate Domain Transfer'
    template_name = 'domain/activate_transfer_domain.html'

    @property
    @memoized
    def active_transfer(self):
        return TransferDomainRequest.get_by_guid(self.guid)

    @property
    def page_context(self):
        if self.active_transfer:
            return {'transfer': self.active_transfer.as_dict()}
        else:
            return {}

    @property
    def page_url(self):
        return self.request.get_full_path()

    def get(self, request, guid, *args, **kwargs):
        self.guid = guid

        if (self.active_transfer and
                self.active_transfer.to_username != request.user.username and
                not request.user.is_superuser):
            return HttpResponseRedirect(reverse("no_permissions"))

        return super(ActivateTransferDomainView, self).get(request, *args, **kwargs)

    def post(self, request, guid, *args, **kwargs):
        self.guid = guid

        if not self.active_transfer:
            raise Http404()

        if self.active_transfer.to_username != request.user.username and not request.user.is_superuser:
            return HttpResponseRedirect(reverse("no_permissions"))

        self.active_transfer.transfer_domain(ip=get_ip(request))
        messages.success(request, _("Successfully transferred ownership of project '{domain}'")
                         .format(domain=self.active_transfer.domain))

        return HttpResponseRedirect(reverse('dashboard_default', args=[self.active_transfer.domain]))

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(ActivateTransferDomainView, self).dispatch(*args, **kwargs)


class DeactivateTransferDomainView(View):

    def post(self, request, guid, *args, **kwargs):

        transfer = TransferDomainRequest.get_by_guid(guid)

        if not transfer:
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

        if (transfer.to_username != request.user.username and
                transfer.from_username != request.user.username and
                not request.user.is_superuser):
            return HttpResponseRedirect(reverse("no_permissions"))

        transfer.active = False
        transfer.save()

        referer = request.META.get('HTTP_REFERER', '/')

        # Do not want to send them back to the activate page
        if referer.endswith(reverse('activate_transfer_domain', args=[guid])):
            messages.info(request,
                          _("Declined ownership of project '{domain}'").format(domain=transfer.domain))
            return HttpResponseRedirect('/')
        else:
            return HttpResponseRedirect(referer)

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(DeactivateTransferDomainView, self).dispatch(*args, **kwargs)


from corehq.apps.smsbillables.forms import PublicSMSRateCalculatorForm
from corehq.apps.smsbillables.async_handlers import PublicSMSRatesAsyncHandler


class PublicSMSRatesView(BasePageView, AsyncHandlerMixin):
    urlname = 'public_sms_rates_view'
    page_title = ugettext_lazy("SMS Rate Calculator")
    template_name = 'domain/admin/global_sms_rates.html'
    async_handlers = [PublicSMSRatesAsyncHandler]

    @use_select2
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
    page_title = ugettext_lazy("SMS Rate Calculator")
    template_name = 'domain/admin/sms_rates.html'
    async_handlers = [
        SMSRatesAsyncHandler,
        SMSRatesSelect2AsyncHandler,
    ]

    @use_select2
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


class BaseCardView(DomainAccountingSettings):

    @property
    def payment_method(self):
        payment_method, __ = StripePaymentMethod.objects.get_or_create(
            web_user=self.request.user.username,
            method_type=PaymentMethodType.STRIPE,
        )
        return payment_method

    def _generic_error(self):
        error = ("Something went wrong while processing your request. "
                 "We're working quickly to resolve the issue. "
                 "Please try again in a few hours.")
        return json_response({'error': error}, status_code=500)

    def _stripe_error(self, e):
        body = e.json_body
        err = body['error']
        return json_response({'error': err['message'],
                              'cards': self.payment_method.all_cards_serialized(self.account)},
                             status_code=502)


class CardView(BaseCardView):
    """View for dealing with a single Credit Card"""
    url_name = "card_view"

    def post(self, request, domain, card_token):
        try:
            card = self.payment_method.get_card(card_token)
            if request.POST.get("is_autopay") == 'true':
                self.payment_method.set_autopay(card, self.account, domain)
            elif request.POST.get("is_autopay") == 'false':
                self.payment_method.unset_autopay(card, self.account)
        except self.payment_method.STRIPE_GENERIC_ERROR as e:
            return self._stripe_error(e)
        except Exception as e:
            return self._generic_error()

        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})

    def delete(self, request, domain, card_token):
        try:
            self.payment_method.remove_card(card_token)
        except self.payment_method.STRIPE_GENERIC_ERROR as e:
            return self._stripe_error(e)

        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})


class CardsView(BaseCardView):
    """View for dealing Credit Cards"""
    url_name = "cards_view"

    def get(self, request, domain):
        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})

    def post(self, request, domain):
        stripe_token = request.POST.get('token')
        autopay = request.POST.get('autopay') == 'true'
        try:
            self.payment_method.create_card(stripe_token, self.account, domain, autopay)
        except self.payment_method.STRIPE_GENERIC_ERROR as e:
            return self._stripe_error(e)
        except Exception as e:
            return self._generic_error()

        return json_response({'cards': self.payment_method.all_cards_serialized(self.account)})


class PasswordResetView(View):
    urlname = "password_reset_confirm"

    def get(self, request, *args, **kwargs):
        extra_context = kwargs.setdefault('extra_context', {})
        extra_context['hide_password_feedback'] = settings.ENABLE_DRACONIAN_SECURITY_FEATURES
        extra_context['implement_password_obfuscation'] = settings.OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE
        return password_reset_confirm(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        extra_context = kwargs.setdefault('extra_context', {})
        extra_context['hide_password_feedback'] = settings.ENABLE_DRACONIAN_SECURITY_FEATURES
        response = password_reset_confirm(request, *args, **kwargs)
        uidb64 = kwargs.get('uidb64')
        uid = urlsafe_base64_decode(uidb64)
        user = User.objects.get(pk=uid)
        couch_user = CouchUser.from_django_user(user)
        clear_login_attempts(couch_user)
        return response
