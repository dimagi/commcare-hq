import copy
import datetime
from decimal import Decimal
import logging
import uuid
from couchdbkit import ResourceNotFound
import dateutil
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.views.generic import View
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.accounting.async_handlers import Select2BillingInfoHandler
from corehq.apps.accounting.decorators import (
    require_billing_admin, requires_privilege_with_fallback,
)
from corehq.apps.accounting.exceptions import PaymentRequestError
from corehq.apps.accounting.payment_handlers import (
    InvoiceStripePaymentHandler, CreditStripePaymentHandler,
)
from corehq.apps.accounting.subscription_changes import DomainDowngradeStatusHandler
from corehq.apps.accounting.forms import EnterprisePlanContactForm
from corehq.apps.accounting.utils import (
    get_change_status, get_privileges, fmt_dollar_amount,
    quantize_accounting_decimal, get_customer_cards,
)
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.smsbillables.async_handlers import SMSRatesAsyncHandler, SMSRatesSelect2AsyncHandler
from corehq.apps.smsbillables.forms import SMSRateCalculatorForm
from corehq.apps.users.models import DomainInvitation
from corehq.apps.fixtures.models import FixtureDataType
from corehq.toggles import NAMESPACE_DOMAIN, all_toggles, CAN_EDIT_EULA
from corehq.util.context_processors import get_domain_type
from dimagi.utils.couch.resource_conflict import retry_resource
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.safestring import mark_safe

from corehq import toggles, privileges, feature_previews
from django_prbac.decorators import requires_privilege_raise404
from django_prbac.exceptions import PermissionDenied
from django_prbac.utils import ensure_request_has_privilege

from corehq.apps.accounting.models import (
    Subscription, CreditLine, SoftwareProductType,
    DefaultProductPlan, SoftwarePlanEdition, BillingAccount,
    BillingAccountType, BillingAccountAdmin,
    Invoice, BillingRecord, InvoicePdf, PaymentMethodType,
    PaymentMethod,
)
from corehq.apps.accounting.usage import FeatureUsageCalculator
from corehq.apps.accounting.user_text import get_feature_name, PricingTable, DESC_BY_EDITION, PricingTableFeatures
from corehq.apps.hqwebapp.models import ProjectSettingsTab
from corehq.apps import receiverwrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404

from django.shortcuts import redirect, render
from corehq.apps.domain.calculations import CALCS, CALC_FNS, CALC_ORDER, dom_calc

from corehq.apps.domain.decorators import (domain_admin_required,
    login_required, require_superuser, login_and_domain_required)
from corehq.apps.domain.forms import (
    DomainGlobalSettingsForm, DomainMetadataForm, SnapshotSettingsForm,
    SnapshotApplicationForm, DomainDeploymentForm, DomainInternalForm,
    ConfirmNewSubscriptionForm, ProBonoForm, EditBillingAccountInfoForm,
    ConfirmSubscriptionRenewalForm, SnapshotFixtureForm,
)
from corehq.apps.domain.models import Domain, LICENSES
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.hqwebapp.views import BaseSectionPageView, BasePageView, CRUDPaginatedViewMixin
from corehq.apps.orgs.models import Organization, OrgRequest, Team
from corehq.apps.domain.forms import ProjectSettingsForm
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.django.email import send_HTML_email

from dimagi.utils.web import get_ip, json_response
from corehq.apps.users.decorators import require_can_edit_web_users
from corehq.apps.receiverwrapper.forms import GenericRepeaterForm, FormRepeaterForm
from corehq.apps.receiverwrapper.models import FormRepeater, CaseRepeater, ShortFormRepeater, AppStructureRepeater, \
    RepeatRecord
from django.contrib import messages
from django.views.decorators.http import require_POST
import json
from dimagi.utils.post import simple_post
import cStringIO
from PIL import Image
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from django.core.cache import cache
from toggle.models import Toggle, generate_toggle_id
from toggle.shortcuts import get_toggle_cache_key, update_toggle_cache, namespaced_item


accounting_logger = logging.getLogger('accounting')

# Domain not required here - we could be selecting it for the first time. See notes domain.decorators
# about why we need this custom login_required decorator


@login_required
def select(request, domain_select_template='domain/select.html'):
    domains_for_user = Domain.active_for_user(request.user)
    if not domains_for_user:
        return redirect('registration_domain', domain_type=get_domain_type(None, request))

    email = request.couch_user.get_email()
    open_invitations = DomainInvitation.by_email(email)

    additional_context = {
        'domains_for_user': domains_for_user,
        'open_invitations': open_invitations,
    }
    return render(request, domain_select_template, additional_context)


@require_superuser
def incomplete_email(request,
                     incomplete_email_template='domain/incomplete_email.html'):
    from corehq.apps.domain.tasks import (
        incomplete_self_started_domains,
        incomplete_domains_to_email
    )
    context = {
        'self_started': incomplete_self_started_domains,
        'dimagi_owned': incomplete_domains_to_email,
    }
    return render(request, incomplete_email_template, context)


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
    page_title = ugettext_noop("Upgrade Required")
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
    def is_billing_admin(self):
        if not hasattr(self.request, 'couch_user'):
            return False
        return BillingAccountAdmin.get_admin_status_and_account(
            self.request.couch_user, self.domain
        )[0]

    @property
    def page_context(self):
        return {
            'domain': self.domain,
            'feature_name': self.feature_name,
            'plan_name': self.required_plan_name,
            'change_subscription_url': reverse(SelectPlanView.urlname,
                                               args=[self.domain]),
            'is_billing_admin': self.is_billing_admin,
        }

    @property
    def missing_privilege(self):
        return self.args[1]

    @property
    def feature_name(self):
        return privileges.Titles.get_name_from_privilege(self.missing_privilege)

    @property
    def required_plan_name(self):
        return DefaultProductPlan.get_lowest_edition_by_domain(
            self.domain_object, [self.missing_privilege]
        )

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
    section_name = ugettext_noop("Project Settings")
    template_name = "settings/base_template.html"

    @property
    def main_context(self):
        main_context = super(BaseProjectSettingsView, self).main_context
        main_context.update({
            'active_tab': ProjectSettingsTab(
                self.request,
                self.urlname,
                domain=self.domain,
                couch_user=self.request.couch_user,
                project=self.request.project
            ),
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
            'commtrack_enabled': self.domain_object.commtrack_enabled, # ideally the template gets access to the domain doc through
                # some other means. otherwise it has to be supplied to every view reachable in that sidebar (every
                # view whose template extends users_base.html); mike says he's refactoring all of this imminently, so
                # i will not worry about it until he is done
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'restrict_superusers': self.domain_object.restrict_superusers,
            'cloudcare_releases':  self.domain_object.cloudcare_releases,
        })
        return context


class EditBasicProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_basic.html'
    urlname = 'domain_basic_info'
    page_title = ugettext_noop("Basic")

    @property
    def can_user_see_meta(self):
        return self.request.couch_user.is_previewer()

    @property
    def autocomplete_fields(self):
        return ['project_type']

    @property
    def can_use_custom_logo(self):
        try:
            ensure_request_has_privilege(
                self.request, privileges.CUSTOM_BRANDING
            )
        except PermissionDenied:
            return False
        return True

    @property
    @memoized
    def basic_info_form(self):
        initial = {
            'default_timezone': self.domain_object.default_timezone,
            'case_sharing': json.dumps(self.domain_object.case_sharing),
            'call_center_enabled': self.domain_object.call_center_config.enabled,
            'call_center_case_owner': self.domain_object.call_center_config.case_owner_id,
            'call_center_case_type': self.domain_object.call_center_config.case_type,
            'commtrack_enabled': self.domain_object.commtrack_enabled,
            'secure_submissions': self.domain_object.secure_submissions,
        }
        if self.request.method == 'POST':
            if self.can_user_see_meta:
                return DomainMetadataForm(
                    self.request.POST,
                    self.request.FILES,
                    user=self.request.couch_user,
                    domain=self.domain_object.name,
                    can_use_custom_logo=self.can_use_custom_logo,
                )
            return DomainGlobalSettingsForm(
                self.request.POST,
                self.request.FILES,
                domain=self.domain_object.name,
                can_use_custom_logo=self.can_use_custom_logo
            )

        if self.can_user_see_meta:
            for attr in [
                'project_type',
                'customer_type',
                'commconnect_enabled',
                'survey_management_enabled',
                'sms_case_registration_enabled',
                'sms_case_registration_type',
                'sms_case_registration_owner_id',
                'sms_case_registration_user_id',
                'restrict_superusers',
                'secure_submissions',
            ]:
                initial[attr] = getattr(self.domain_object, attr)
            initial.update({
                'is_test': self.domain_object.is_test,
                'cloudcare_releases': self.domain_object.cloudcare_releases,
            })

            return DomainMetadataForm(
                can_use_custom_logo=self.can_use_custom_logo,
                user=self.request.couch_user,
                domain=self.domain_object.name,
                initial=initial
            )
        return DomainGlobalSettingsForm(
            initial=initial,
            domain=self.domain_object.name,
            can_use_custom_logo=self.can_use_custom_logo
        )

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
        return self.get(request, *args, **kwargs)


class EditDeploymentProjectInfoView(BaseEditProjectInfoView):
    template_name = 'domain/admin/info_deployment.html'
    urlname = 'domain_deployment_info'
    page_title = ugettext_noop("Deployment")

    @property
    def autocomplete_fields(self):
        return ['city', 'countries', 'region']

    @property
    @memoized
    def deployment_info_form(self):
        if self.request.method == 'POST':
            return DomainDeploymentForm(self.request.POST)

        initial = {
            'deployment_date': self.domain_object.deployment.date.date if self.domain_object.deployment.date else "",
            'public': 'true' if self.domain_object.deployment.public else 'false',
        }
        for attr in [
            'city',
            'countries',
            'region',
            'description',
        ]:
            initial[attr] = getattr(self.domain_object.deployment, attr)
        return DomainDeploymentForm(initial=initial)

    @property
    def page_context(self):
        return {
            'deployment_info_form': self.deployment_info_form,
        }

    def post(self, request, *args, **kwargs):
        if self.deployment_info_form.is_valid():
            if self.deployment_info_form.save(self.domain_object):
                messages.success(request,
                                 _("The deployment information for project %s was successfully updated!")
                                 % self.domain_object.name)
            else:
                messages.error(request, _("There seems to have been an error. Please try again!"))

        return self.get(request, *args, **kwargs)


class EditMyProjectSettingsView(BaseProjectSettingsView):
    template_name = 'domain/admin/my_project_settings.html'
    urlname = 'my_project_settings'
    page_title = ugettext_noop("My Timezone")

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


@require_POST
@require_can_edit_web_users
def drop_repeater(request, domain, repeater_id):
    rep = FormRepeater.get(repeater_id)
    rep.retire()
    messages.success(request, "Form forwarding stopped!")
    return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[domain]))


@require_POST
@require_can_edit_web_users
def test_repeater(request, domain):
    url = request.POST["url"]
    repeater_type = request.POST['repeater_type']
    form = GenericRepeaterForm(
        {"url": url},
        domain=domain,
        repeater_class=receiverwrapper.models.repeater_types[repeater_type]
    )
    if form.is_valid():
        url = form.cleaned_data["url"]
        # now we fake a post
        def _stub(repeater_type):
            if 'case' in repeater_type.lower():
                return CaseBlock(
                    case_id='test-case-%s' % uuid.uuid4().hex,
                    create=True,
                    case_type='test',
                    case_name='test case',
                    version=V2,
                ).as_string()
            else:
                return "<?xml version='1.0' ?><data id='test'><TestString>Test post from CommCareHQ on %s</TestString></data>" % \
                       (datetime.datetime.utcnow())

        fake_post = _stub(repeater_type)
        try:
            resp = simple_post(fake_post, url)
            if 200 <= resp.status < 300:
                return HttpResponse(json.dumps({"success": True,
                                                "response": resp.read(),
                                                "status": resp.status}))
            else:
                return HttpResponse(json.dumps({"success": False,
                                                "response": resp.read(),
                                                "status": resp.status}))

        except Exception, e:
            errors = str(e)
        return HttpResponse(json.dumps({"success": False, "response": errors}))
    else:
        return HttpResponse(json.dumps({"success": False, "response": "Please enter a valid url."}))


def autocomplete_fields(request, field):
    prefix = request.GET.get('prefix', '')
    results = Domain.field_by_prefix(field, prefix)
    return HttpResponse(json.dumps(results))

def logo(request, domain):
    logo = Domain.get_by_name(domain).get_custom_logo()
    if logo is None:
        raise Http404()

    return HttpResponse(logo[0], mimetype=logo[1])


class DomainAccountingSettings(BaseAdminProjectSettingsView):

    @method_decorator(login_and_domain_required)
    @method_decorator(require_billing_admin())
    def dispatch(self, request, *args, **kwargs):
        return super(DomainAccountingSettings, self).dispatch(request, *args, **kwargs)

    @property
    def main_context(self):
        context = super(DomainAccountingSettings, self).main_context
        if (hasattr(self.request, 'is_billing_admin')
            and not self.request.is_billing_admin
            and self.request.couch_user.is_superuser
        ):
            # check to see if superuser is accounting admin
            # If not, notify that they should change it.
            from corehq.apps.accounting.utils import is_accounting_admin
            has_privs = is_accounting_admin(self.request.user)
            if has_privs:
                context.update(is_ops_user_but_not_admin=True)
                messages.info(
                    self.request, mark_safe(_(
                        "Hi there, Operations User. You are currently not "
                        "a Billing Admin for this account.<br />"
                        "<a href='%(url)s' class='btn btn-primary'>"
                        "Change This</a>"
                    ) % {
                        'url': reverse(AddOpsUserAsDomainAdminView.urlname,
                                       args=[self.domain]),
                    })
                )
        return context

    @property
    @memoized
    def product(self):
        return SoftwareProductType.get_type_by_domain(self.domain_object)

    @property
    @memoized
    def account(self):
        return BillingAccount.get_account_by_domain(self.domain)

    @property
    def current_subscription(self):
        return Subscription.get_subscribed_plan_by_domain(self.domain_object)[1]


class AddOpsUserAsDomainAdminView(BaseAdminProjectSettingsView):
    urlname = 'domain_ops_billing_admin'
    template_name = 'domain/new_ops_billing_admin.html'
    page_title = ugettext_noop("Join Billing Account Admins")

    @method_decorator(requires_privilege_raise404(privileges.ACCOUNTING_ADMIN))
    def dispatch(self, request, *args, **kwargs):
        is_domain_admin, self.account = BillingAccountAdmin.get_admin_status_and_account(
            request.couch_user, self.domain
        )
        if is_domain_admin:
            return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
        return super(AddOpsUserAsDomainAdminView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        admin = BillingAccountAdmin.objects.get_or_create(
            web_user=request.user.username,
            domain=self.domain,
        )[0]
        self.account.billing_admins.add(admin)
        self.account.save()
        messages.success(
            request,
            _("Successfully added as Billing Admin for project %s" % self.domain)
        )
        return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))


class DomainSubscriptionView(DomainAccountingSettings):
    urlname = 'domain_subscription_view'
    template_name = 'domain/current_subscription.html'
    page_title = ugettext_noop("Current Subscription")

    @property
    def can_purchase_credits(self):
        return BillingAccountAdmin.objects.filter(
            web_user=self.request.user.username, domain=self.domain
        ).exists()

    @property
    def plan(self):
        plan_version, subscription = Subscription.get_subscribed_plan_by_domain(self.domain_object)
        date_end = None
        next_subscription = {
            'exists': False,
            'can_renew': False,
        }
        cards = None
        general_credits = None
        if subscription:
            cards = get_customer_cards(self.account, self.request.user.username, self.domain)
            date_end = (subscription.date_end.strftime("%d %B %Y")
                        if subscription.date_end is not None else "--")

            if subscription.date_end is not None:
                if subscription.is_renewed:
                    next_subscription.update({
                        'exists': True,
                        'date_start': subscription.next_subscription.date_start.strftime("%d %B %Y"),
                    })
                else:
                    days_left = (subscription.date_end - datetime.date.today()).days
                    next_subscription.update({
                        'can_renew': days_left <= 30,
                        'renew_url': reverse(ConfirmSubscriptionRenewalView.urlname, args=[self.domain]),
                    })
            general_credits = CreditLine.get_credits_by_subscription_and_features(subscription)
        elif self.account is not None:
            general_credits = CreditLine.get_credits_for_account(self.account)
        if general_credits:
            general_credits = self._fmt_credit(self._credit_grand_total(general_credits))

        products = self.get_product_summary(plan_version, self.account, subscription)
        info = {
            'products': products,
            'is_multiproduct': len(products) > 1,
            'features': self.get_feature_summary(plan_version, self.account, subscription),
            'general_credit': general_credits,
            'css_class': "label-plan %s" % plan_version.plan.edition.lower(),
            'is_dimagi_subscription': subscription.do_not_invoice if subscription is not None else False,
            'is_trial': subscription.is_trial if subscription is not None else False,
            'date_start': (subscription.date_start.strftime("%d %B %Y")
                           if subscription is not None else None),
            'date_end': date_end,
            'cards': cards,
            'next_subscription': next_subscription,
        }
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
        product_summary = []
        for product_rate in plan_version.product_rates.all():
            product_info = {
                'name': product_rate.product.product_type,
                'monthly_fee': _("USD %s /month") % product_rate.monthly_fee,
                'credit': None,
                'type': product_rate.product.product_type,
            }
            credit_lines = None
            if subscription is not None:
                credit_lines = CreditLine.get_credits_by_subscription_and_features(
                    subscription, product_type=product_rate.product.product_type
                )
            elif account is not None:
                credit_lines = CreditLine.get_credits_for_account(
                    account, product_type=product_rate.product.product_type
                )
            if credit_lines:
                product_info['credit'] = self._fmt_credit(self._credit_grand_total(credit_lines))
            product_summary.append(product_info)
        return product_summary

    def get_feature_summary(self, plan_version, account, subscription):
        feature_summary = []
        for feature_rate in plan_version.feature_rates.all():
            usage = FeatureUsageCalculator(feature_rate, self.domain).get_usage()
            feature_info = {
                'name': get_feature_name(feature_rate.feature.feature_type, self.product),
                'usage': usage,
                'remaining': feature_rate.monthly_limit - usage,
                'credit': self._fmt_credit(),
                'type': feature_rate.feature.feature_type,
            }

            credit_lines = None
            if subscription is not None:
                credit_lines = CreditLine.get_credits_by_subscription_and_features(
                    subscription, feature_type=feature_rate.feature.feature_type
                )
            elif account is not None:
                credit_lines = CreditLine.get_credits_for_account(
                    account, feature_type=feature_rate.feature.feature_type)
            if credit_lines:
                feature_info['credit'] = self._fmt_credit(self._credit_grand_total(credit_lines))

            feature_summary.append(feature_info)
        return feature_summary

    @property
    def page_context(self):
        return {
            'plan': self.plan,
            'change_plan_url': reverse(SelectPlanView.urlname, args=[self.domain]),
            'can_purchase_credits': self.can_purchase_credits,
            'process_payment_url': reverse(CreditsStripePaymentView.urlname,
                                           args=[self.domain]),
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'sms_rate_calc_url': reverse(SMSRatesView.urlname,
                                         args=[self.domain])
        }


class EditExistingBillingAccountView(DomainAccountingSettings, AsyncHandlerMixin):
    template_name = 'domain/update_billing_contact_info.html'
    urlname = 'domain_update_billing_info'
    page_title = ugettext_noop("Billing Contact Information")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    @memoized
    def billing_info_form(self):
        if self.request.method == 'POST':
            return EditBillingAccountInfoForm(
                self.account, self.domain, self.request.couch_user.username, data=self.request.POST
            )
        return EditBillingAccountInfoForm(self.account, self.domain, self.request.couch_user.username)

    def dispatch(self, request, *args, **kwargs):
        if self.account is None:
            raise Http404()
        return super(EditExistingBillingAccountView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'billing_account_info_form': self.billing_info_form,
        }

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
    page_title = ugettext_noop("Billing Statements")

    limit_text = ugettext_noop("statements per page")
    empty_notification = ugettext_noop("No Billing Statements match the current criteria.")
    loading_message = ugettext_noop("Loading statements...")

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def stripe_cards(self):
        return get_customer_cards(self.account, self.request.user.username, self.domain)

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
            'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
            'process_payment_url': reverse(InvoiceStripePaymentView.urlname,
                                           args=[self.domain]),
            'stripe_cards': self.stripe_cards,
        })
        return pagination_context

    @property
    def can_pay_invoices(self):
        return BillingAccountAdmin.objects.filter(
            web_user=self.request.user.username, domain=self.domain
        ).exists()

    @property
    def paginated_list(self):
        for invoice in self.paginated_invoices.page(self.page).object_list:
            try:
                last_billing_record = BillingRecord.objects.filter(
                    invoice=invoice
                ).latest('date_created')
                if invoice.date_paid is not None:
                    payment_status = (_("Paid on %s.")
                                      % invoice.date_paid.strftime("%d %B %Y"))
                    payment_class = "label label-inverse"
                else:
                    payment_status = _("Not Paid")
                    payment_class = "label label-important"
                date_due = (invoice.date_due.strftime("%d %B %Y")
                            if invoice.date_paid is None else _("Already Paid"))
                yield {
                    'itemData': {
                        'id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'start': invoice.date_start.strftime("%d %B %Y"),
                        'end': invoice.date_end.strftime("%d %B %Y"),
                        'plan': invoice.subscription.plan_version.user_facing_description,
                        'payment_status': payment_status,
                        'payment_class': payment_class,
                        'date_due': date_due,
                        'pdfUrl': reverse(
                            BillingStatementPdfView.urlname,
                            args=[self.domain, last_billing_record.pdf_data_id]
                        ),
                        'canMakePayment': (invoice.date_paid is None
                                           and self.can_pay_invoices),
                        'balance': "%s" % quantize_accounting_decimal(invoice.balance),
                    },
                    'template': 'statement-row-template',
                }
            except BillingRecord.DoesNotExist:
                logging.error(
                    "An invoice was generated for %(invoice_id)d "
                    "(domain: %(domain)s), but no billing record!" % {
                        'invoice_id': invoice.id,
                        'domain': self.domain,
                    })

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
        raise NotImplementedError("you must impmement the property account")

    @property
    @memoized
    def billing_admin(self):
        try:
            admin = BillingAccountAdmin.objects.get(
                web_user=self.request.user.username, domain=self.domain
            )
            # verify that this admin is still tied to the account for
            # the invoice
            if not self.account.billing_admins.filter(
                    pk=admin.pk).exists():
                raise PaymentRequestError(
                    "The billing admin provided is not an account admin for "
                    "the account this invoice is tied to."
                )
            return admin
        except BillingAccountAdmin.DoesNotExist:
            raise PaymentRequestError(
                "Could not find an appropriate billing admin for the "
                "logged in user."
            )

    def get_or_create_payment_method(self):
        return PaymentMethod.objects.get_or_create(
            account=self.account,
            billing_admin=self.billing_admin,
            method_type=PaymentMethodType.STRIPE,
        )[0]

    def get_payment_handler(self):
        """Returns a StripePaymentHandler object
        """
        raise NotImplementedError("You must impmenent get_payment_handler()")

    def post(self, request, *args, **kwargs):
        try:
            payment_handler = self.get_payment_handler()
            response = payment_handler.process_request(request)
        except PaymentRequestError as e:
            accounting_logger.error(
                "[BILLING] Failed to process Stripe Payment due to bad "
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
            self.domain, created_by=self.request.user.username,
            account_type=BillingAccountType.USER_CREATED,
        )[0]

    def get_payment_handler(self):
        return CreditStripePaymentHandler(
            self.get_or_create_payment_method(),
            self.account,
            subscription=Subscription.get_subscribed_plan_by_domain(self.domain_object)[1],
            product_type=self.request.POST.get('product'),
            feature_type=self.request.POST.get('feature'),
        )


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
            self.get_or_create_payment_method(), self.invoice
        )


class BillingStatementPdfView(View):
    urlname = 'domain_billing_statement_download'

    @method_decorator(login_and_domain_required)
    @method_decorator(require_billing_admin())
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

        # verify domain
        try:
            invoice = Invoice.objects.get(pk=invoice_pdf.invoice_id)
        except Invoice.DoesNotExist:
            raise Http404()
        if invoice.subscription.subscriber.domain != domain:
            raise Http404()

        filename = "%(pdf_id)s_%(domain)s_%(edition)s_%(filename)s" % {
            'pdf_id': invoice_pdf._id,
            'domain': domain,
            'edition': DESC_BY_EDITION[invoice.subscription.plan_version.plan.edition]['name'],
            'filename': invoice_pdf.get_filename(invoice),
        }
        try:
            data = invoice_pdf.get_data(invoice)
            response = HttpResponse(data, content_type='application/pdf')
            response['Content-Disposition'] = 'inline;filename="%s' % filename
        except Exception as e:
            logging.error('[Billing] Fetching invoice PDF failed: %s' % e)
            return HttpResponse(_("Could not obtain billing statement. "
                                  "An issue has been submitted."))
        return response


class SelectPlanView(DomainAccountingSettings):
    template_name = 'domain/select_plan.html'
    urlname = 'domain_select_plan'
    page_title = ugettext_noop("Change Plan")
    step_title = ugettext_noop("Select Plan")
    edition = None

    @property
    def edition_name(self):
        if self.edition:
            return DESC_BY_EDITION[self.edition]['name'].encode('utf-8')

    @property
    def is_non_ops_superuser(self):
        if not self.request.couch_user.is_superuser:
            return False
        try:
            ensure_request_has_privilege(
                self.request, privileges.ACCOUNTING_ADMIN)
            return False
        except PermissionDenied:
            return True

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
        return [
            {
                'title': _("1. Select a Plan%s") % (" (%s)" % self.edition_name if self.edition_name else ""),
                'url': reverse(SelectPlanView.urlname, args=[self.domain]),
            }
        ]

    @property
    def main_context(self):
        context = super(SelectPlanView, self).main_context
        context.update({
            'steps': self.steps,
            'step_title': self.step_title,
        })
        return context

    @property
    def page_context(self):
        return {
            'pricing_table': PricingTable.get_table_by_product(self.product, domain=self.domain),
            'current_edition': (self.current_subscription.plan_version.plan.edition.lower()
                                if self.current_subscription is not None
                                and not self.current_subscription.is_trial
                                else ""),
            'is_non_ops_superuser': self.is_non_ops_superuser,
        }


class SelectedEnterprisePlanView(SelectPlanView):
    template_name = 'domain/selected_enterprise_plan.html'
    urlname = 'enterprise_request_quote'
    step_title = ugettext_noop("Contact Dimagi")
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
    step_title = ugettext_noop("Confirm Plan")

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
        return DefaultProductPlan.get_default_plan_by_domain(self.domain, self.edition).plan.get_version()

    @property
    def downgrade_messages(self):
        current_plan_version, subscription = Subscription.get_subscribed_plan_by_domain(self.domain_object)
        if subscription is None:
            current_plan_version = None
        downgrades = get_change_status(current_plan_version, self.selected_plan_version)[1]
        downgrade_handler = DomainDowngradeStatusHandler(
            self.domain_object, self.selected_plan_version, downgrades,
            web_user=self.request.user.username
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
        if self.edition == SoftwarePlanEdition.ENTERPRISE and not self.request.couch_user.is_superuser:
            return HttpResponseRedirect(reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]))
        return super(ConfirmSelectedPlanView, self).get(request, *args, **kwargs)


class ConfirmBillingAccountInfoView(ConfirmSelectedPlanView, AsyncHandlerMixin):
    template_name = 'domain/confirm_billing_info.html'
    urlname = 'confirm_billing_account_info'
    step_title = ugettext_noop("Confirm Billing Information")
    is_new = False
    async_handlers = [
        Select2BillingInfoHandler,
    ]

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
            self.domain, created_by=self.request.couch_user.username, account_type=BillingAccountType.USER_CREATED,
        )
        return account

    @property
    @memoized
    def is_form_post(self):
        return 'billing_admins' in self.request.POST

    @property
    @memoized
    def billing_account_info_form(self):
        initial = None
        if self.edition == SoftwarePlanEdition.ENTERPRISE and self.request.couch_user.is_superuser:
            initial = {
                'company_name': "Dimagi",
                'first_line': "585 Massachusetts Ave",
                'second_line': "Suite 3",
                'city': "Cambridge",
                'state_province_region': "MA",
                'postal_code': "02139",
                'country': "US",

            }
        if self.request.method == 'POST' and self.is_form_post:
            return ConfirmNewSubscriptionForm(
                self.account, self.domain, self.request.couch_user.username,
                self.selected_plan_version, self.current_subscription, data=self.request.POST, initial=initial
            )
        return ConfirmNewSubscriptionForm(self.account, self.domain, self.request.couch_user.username,
                                          self.selected_plan_version, self.current_subscription, initial=initial)

    @property
    def page_context(self):
        return {
            'billing_account_info_form': self.billing_account_info_form,
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.edition == SoftwarePlanEdition.ENTERPRISE and not self.request.couch_user.is_superuser:
            return HttpResponseRedirect(reverse(SelectedEnterprisePlanView.urlname, args=[self.domain]))
        if self.is_form_post and self.billing_account_info_form.is_valid():
            is_saved = self.billing_account_info_form.save()
            software_plan_name = DESC_BY_EDITION[self.selected_plan_version.plan.edition]['name'].encode('utf-8')
            if not is_saved:
                messages.error(
                    request, _("It appears there was an issue subscribing your project to the %s Software Plan. You "
                               "may try resubmitting, but if that doesn't work, rest assured someone will be "
                               "contacting you shortly.") % software_plan_name)
            else:
                messages.success(
                    request, _("Your project has been successfully subscribed to the %s Software Plan."
                               % software_plan_name)
                )
                return HttpResponseRedirect(reverse(DomainSubscriptionView.urlname, args=[self.domain]))
        return super(ConfirmBillingAccountInfoView, self).post(request, *args, **kwargs)


class ConfirmSubscriptionRenewalView(DomainAccountingSettings, AsyncHandlerMixin):
    template_name = 'domain/confirm_subscription_renewal.html'
    urlname = 'domain_subscription_renewal'
    page_title = ugettext_noop("Renew Plan")
    async_handlers = [
        Select2BillingInfoHandler,
    ]

    @property
    @memoized
    def subscription(self):
        subscription = Subscription.get_subscribed_plan_by_domain(self.domain_object)[1]
        if subscription is None:
            raise Http404
        if subscription.is_renewed:
            raise Http404
        return subscription

    @property
    @memoized
    def next_plan_version(self):
        current_privs = get_privileges(self.subscription.plan_version)
        plan_version = DefaultProductPlan.get_lowest_edition_by_domain(
            self.domain, current_privs, return_plan=True,
        )
        if plan_version is None:
            logging.error("[BILLING] Could not find a matching renwabled plan "
                          "for %(domain)s, subscription number %(sub_pk)s." % {
                'domain': self.domain,
                'sub_pk': self.subscription.pk
            })
            raise Http404
        return plan_version

    @property
    @memoized
    def confirm_form(self):
        if self.request.method == 'POST':
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

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
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


class ExchangeSnapshotsView(BaseAdminProjectSettingsView):
    template_name = 'domain/snapshot_settings.html'
    urlname = 'domain_snapshot_settings'
    page_title = ugettext_noop("CommCare Exchange")

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
    page_title = ugettext_noop("Publish New Version")
    strict_domain_fetching = True

    @property
    def parent_pages(self):
        return [{
            'title': ExchangeSnapshotsView.page_title,
            'url': reverse(ExchangeSnapshotsView.urlname, args=[self.domain]),
        }]

    @property
    def page_context(self):
        context = {
            'form': self.snapshot_settings_form,
            'app_forms': self.app_forms,
            'fixture_forms': self.fixture_forms,
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
        return (self.domain_object.get_organization()
                and self.request.couch_user.is_org_admin(self.domain_object.get_organization().name))

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
                published_apps[base_app_id] = app
        return published_apps

    @property
    def app_forms(self):
        app_forms = []
        for app in self.domain_object.applications():
            app = app.get_latest_saved() or app
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
            form = SnapshotSettingsForm(self.request.POST, self.request.FILES)
            form.dom = self.domain_object
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

        return SnapshotSettingsForm(initial=initial)

    @property
    @memoized
    def has_published_apps(self):
        for app in self.domain_object.applications():
            app = app.get_latest_saved() or app
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

            ignore = []
            if not request.POST.get('share_reminders', False):
                ignore.append('CaseReminderHandler')

            copy_by_id = set()
            for k in request.POST.keys():
                if k.endswith("-publish"):
                    copy_by_id.add(k[:-len("-publish")])

            old = self.domain_object.published_snapshot()
            new_domain = self.domain_object.save_snapshot(ignore=ignore,
                                                          copy_by_id=copy_by_id)
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
            publish_on_submit = request.POST.get('publish_on_submit', "no") == "yes"

            image = self.snapshot_settings_form.cleaned_data['image']
            if image:
                new_domain.image_path = image.name
                new_domain.image_type = image.content_type
            elif request.POST.get('old_image', False):
                new_domain.image_path = old.image_path
                new_domain.image_type = old.image_type
            new_domain.save()

            if publish_on_submit:
                _publish_snapshot(request, self.domain_object, published_snapshot=new_domain)
            else:
                new_domain.published = False
                new_domain.save()

            if image:
                im = Image.open(image)
                out = cStringIO.StringIO()
                im.thumbnail((200, 200), Image.ANTIALIAS)
                im.save(out, new_domain.image_type.split('/')[-1])
                new_domain.put_attachment(content=out.getvalue(), name=image.name)
            elif request.POST.get('old_image', False):
                new_domain.put_attachment(content=old.fetch_attachment(old.image_path), name=new_domain.image_path)

            for application in new_domain.full_applications():
                original_id = application.copied_from._id
                application.name = request.POST["%s-name" % original_id]
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

            if new_domain is None:
                messages.error(request, _("Version creation failed; please try again"))
            else:
                messages.success(request, (_("Created a new version of your app. This version will be posted to "
                                             "CommCare Exchange pending approval by admins.") if publish_on_submit
                                           else _("Created a new version of your app.")))
                return redirect(ExchangeSnapshotsView.urlname, self.domain)
        return self.get(request, *args, **kwargs)


class ManageProjectMediaView(BaseAdminProjectSettingsView):
    urlname = 'domain_manage_multimedia'
    page_title = ugettext_noop("Multimedia Sharing")
    template_name = 'domain/admin/media_manager.html'

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
            'licenses': LICENSES.items(),
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


class RepeaterMixin(object):

    @property
    def friendly_repeater_names(self):
        return {
            'FormRepeater': _("Forms"),
            'CaseRepeater': _("Cases"),
            'ShortFormRepeater': _("Form Stubs"),
            'AppStructureRepeater': _("App Schema Changes"),
        }


class DomainForwardingOptionsView(BaseAdminProjectSettingsView, RepeaterMixin):
    urlname = 'domain_forwarding'
    page_title = ugettext_noop("Data Forwarding")
    template_name = 'domain/admin/domain_forwarding.html'

    @property
    def repeaters(self):
        available_repeaters = [
            FormRepeater, CaseRepeater, ShortFormRepeater, AppStructureRepeater,
        ]
        return [(r.__name__, r.by_domain(self.domain), self.friendly_repeater_names[r.__name__])
                for r in available_repeaters]

    @property
    def page_context(self):
        return {
            'repeaters': self.repeaters,
            'pending_record_count': RepeatRecord.count(self.domain),
        }


class AddRepeaterView(BaseAdminProjectSettingsView, RepeaterMixin):
    urlname = 'add_repeater'
    page_title = ugettext_noop("Forward Data")
    template_name = 'domain/admin/add_form_repeater.html'
    repeater_form_class = GenericRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.repeater_type])

    @property
    def parent_pages(self):
        return [{
            'title': DomainForwardingOptionsView.page_title,
            'url': reverse(DomainForwardingOptionsView.urlname, args=[self.domain]),
        }]

    @property
    def repeater_type(self):
        return self.kwargs['repeater_type']

    @property
    def page_name(self):
        return "Forward %s" % self.friendly_repeater_names.get(self.repeater_type, "Data")

    @property
    @memoized
    def repeater_class(self):
        try:
            return receiverwrapper.models.repeater_types[self.repeater_type]
        except KeyError:
            raise Http404()

    @property
    @memoized
    def add_repeater_form(self):
        if self.request.method == 'POST':
            return self.repeater_form_class(
                self.request.POST,
                domain=self.domain,
                repeater_class=self.repeater_class
            )
        return self.repeater_form_class(
            domain=self.domain,
            repeater_class=self.repeater_class
        )

    @property
    def page_context(self):
        return {
            'form': self.add_repeater_form,
            'repeater_type': self.repeater_type,
        }

    def make_repeater(self):
        repeater = self.repeater_class(
            domain=self.domain,
            url=self.add_repeater_form.cleaned_data['url'],
            format=self.add_repeater_form.cleaned_data['format']
        )
        return repeater

    def post(self, request, *args, **kwargs):
        if self.add_repeater_form.is_valid():
            repeater = self.make_repeater()
            repeater.save()
            messages.success(request, _("Forwarding set up to %s" % repeater.url))
            return HttpResponseRedirect(reverse(DomainForwardingOptionsView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


class AddFormRepeaterView(AddRepeaterView):
    urlname = 'add_form_repeater'
    repeater_form_class = FormRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def make_repeater(self):
        repeater = super(AddFormRepeaterView, self).make_repeater()
        repeater.exclude_device_reports = self.add_repeater_form.cleaned_data['exclude_device_reports']
        return repeater


class OrgSettingsView(BaseAdminProjectSettingsView):
    template_name = 'domain/orgs_settings.html'
    urlname = 'domain_org_settings'
    page_title = ugettext_noop("Organization")

    @method_decorator(requires_privilege_with_fallback(privileges.CROSS_PROJECT_REPORTS))
    def dispatch(self, request, *args, **kwargs):
        return super(OrgSettingsView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        domain = self.domain_object
        org_users = []
        teams = Team.get_by_domain(domain.name)
        for team in teams:
            for user in team.get_members():
                user.team_id = team.get_id
                user.team = team.name
                org_users.append(user)

        for user in org_users:
            user.current_domain = domain.name

        all_orgs = Organization.get_all()

        return {
            "project": domain,
            'domain': domain.name,
            "organization": Organization.get_by_name(getattr(domain, "organization", None)),
            "org_users": org_users,
            "all_orgs": all_orgs,
        }


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
    page_title = ugettext_noop("Project Information")
    template_name = 'domain/internal_settings.html'
    strict_domain_fetching = True

    @property
    @memoized
    def internal_settings_form(self):
        can_edit_eula = CAN_EDIT_EULA.enabled(self.request.couch_user.username)
        if self.request.method == 'POST':
            return DomainInternalForm(can_edit_eula, self.request.POST)
        initial = {}
        internal_attrs = [
            'sf_contract_id',
            'sf_account_id',
            'commcare_edition',
            'services',
            'initiative',
            'workshop_region',
            'project_state',
            'area',
            'sub_area',
            'organization_name',
            'notes',
            'platform',
            'self_started',
            'using_adm',
            'using_call_center',
            'project_manager',
            'phone_model',
            'goal_time_period',
            'goal_followup_rate',
            'commtrack_domain',
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
        return DomainInternalForm(can_edit_eula, initial=initial)

    @property
    def page_context(self):
        return {
            'project': self.domain_object,
            'form': self.internal_settings_form,
            'areas': dict([(a["name"], a["sub_areas"]) for a in settings.INTERNAL_DATA["area"]]),
        }

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
                send_mail('Custom EULA or data use flags changed for {}'.format(self.domain),
                          message, settings.DEFAULT_FROM_EMAIL, [settings.EULA_CHANGE_EMAIL])

            messages.success(request, _("The internal information for project %s was successfully updated!")
                                      % self.domain)
        else:
            messages.error(request, _("There seems to have been an error. Please try again!"))
        return self.get(request, *args, **kwargs)


class EditInternalCalculationsView(BaseInternalDomainSettingsView):
    urlname = 'domain_internal_calculations'
    page_title = ugettext_noop("Calculated Properties")
    template_name = 'domain/internal_calculations.html'

    @property
    def page_context(self):
        return {
            'calcs': CALCS,
            'order': CALC_ORDER,
        }


@login_and_domain_required
@require_superuser
def calculated_properties(request, domain):
    calc_tag = request.GET.get("calc_tag", '').split('--')
    extra_arg = calc_tag[1] if len(calc_tag) > 1 else ''
    calc_tag = calc_tag[0]

    if not calc_tag or calc_tag not in CALC_FNS.keys():
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
    url_base = Site.objects.get_current().domain
    params = {"domain": domain, "snapshot": snapshot, "published_by": published_by, "url_base": url_base}
    text_content = render_to_string("domain/email/published_app_notification.txt", params)
    html_content = render_to_string("domain/email/published_app_notification.html", params)
    recipients = settings.EXCHANGE_NOTIFICATION_RECIPIENTS
    subject = "New App on Exchange: %s" % snapshot.title
    try:
        for recipient in recipients:
            send_HTML_email(subject, recipient, html_content, text_content=text_content,
                            email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, but the message was:\n%s" % text_content)

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


class ProBonoMixin():
    page_title = ugettext_noop("Pro-Bono Application")
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

    @property
    def requesting_domain(self):
        return self.pro_bono_form.cleaned_data['domain']


class ProBonoView(ProBonoMixin, DomainAccountingSettings):
    template_name = 'domain/pro_bono/domain.html'
    urlname = 'pro_bono'
    use_domain_field = False

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
    page_title = ugettext_noop("Feature Previews")
    template_name = 'domain/admin/feature_previews.html'

    @memoized
    def features(self):
        features = []
        for preview_name in dir(feature_previews):
            if not preview_name.startswith('__'):
                preview = getattr(feature_previews, preview_name)
                if isinstance(preview, feature_previews.FeaturePreview) and preview.has_privilege(self.request):
                    features.append((preview, preview.enabled(self.domain)))

        return features

    def get_toggle(self, slug):
        if not slug in [f.slug for f, _ in self.features()]:
            raise Http404()
        try:
            return Toggle.get(slug)
        except ResourceNotFound:
            return Toggle(slug=slug)

    @property
    def page_context(self):
        return {
            'features': self.features(),
        }

    def post(self, request, *args, **kwargs):
        for feature, enabled in self.features():
            self.update_feature(feature, enabled, feature.slug in request.POST)

        return redirect('feature_previews', domain=self.domain)

    def update_feature(self, feature, current_state, new_state):
        if current_state != new_state:
            slug = feature.slug
            toggle = self.get_toggle(slug)
            item = namespaced_item(self.domain, NAMESPACE_DOMAIN)
            if new_state:
                if not item in toggle.enabled_users:
                    toggle.enabled_users.append(item)
            else:
                toggle.enabled_users.remove(item)
            toggle.save()
            update_toggle_cache(slug, item, new_state)

            if feature.save_fn is not None:
                feature.save_fn(self.domain, new_state)


class FeatureFlagsView(BaseAdminProjectSettingsView):
    urlname = 'domain_feature_flags'
    page_title = ugettext_noop("Feature Flags")
    template_name = 'domain/admin/feature_flags.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(FeatureFlagsView, self).dispatch(request, *args, **kwargs)

    @memoized
    def enabled_flags(self):
        def _sort_key(toggle_enabled_tuple):
            return (not toggle_enabled_tuple[1], toggle_enabled_tuple[0].label)
        return sorted(
            [(toggle, toggle.enabled(self.domain)) for toggle in all_toggles()],
            key=_sort_key,
        )

    @property
    def page_context(self):
        return {
            'flags': self.enabled_flags(),
        }


class SMSRatesView(BaseAdminProjectSettingsView, AsyncHandlerMixin):
    urlname = 'domain_sms_rates_view'
    page_title = ugettext_noop("SMS Rate Calculator")
    template_name = 'domain/admin/sms_rates.html'
    async_handlers = [
        SMSRatesAsyncHandler,
        SMSRatesSelect2AsyncHandler,
    ]

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


@require_POST
@domain_admin_required
def org_request(request, domain):
    org_name = request.POST.get("org_name", None)
    org = Organization.get_by_name(org_name)
    if org:
        org_request = OrgRequest.get_requests(org_name, domain=domain, user_id=request.couch_user.get_id)
        if not org_request:
            org_request = OrgRequest(organization=org_name, domain=domain,
                requested_by=request.couch_user.get_id, requested_on=datetime.datetime.utcnow())
            org_request.save()
            _send_request_notification_email(request, org, domain)
            messages.success(request,
                "Your request was submitted. The admin of organization %s can now choose to manage the project %s" %
                (org_name, domain))
        else:
            messages.error(request, "You've already submitted a request to this organization")
    else:
        messages.error(request, "The organization '%s' does not exist" % org_name)
    return HttpResponseRedirect(reverse('domain_org_settings', args=[domain]))

def _send_request_notification_email(request, org, dom):
    url_base = Site.objects.get_current().domain
    params = {"org": org, "dom": dom, "requestee": request.couch_user, "url_base": url_base}
    text_content = render_to_string("domain/email/org_request_notification.txt", params)
    html_content = render_to_string("domain/email/org_request_notification.html", params)
    recipients = [member.email for member in org.get_members() if member.is_org_admin(org.name)]
    subject = "New request to add a project to your organization! -- CommcareHQ"
    try:
        for recipient in recipients:
            send_HTML_email(subject, recipient, html_content, text_content=text_content,
                            email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning("Can't send notification email, but the message was:\n%s" % text_content)
