import calendar
import datetime
from decimal import Decimal
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from corehq import Domain, privileges
from corehq.util.quickcache import quickcache
from corehq.apps.accounting.exceptions import (
    AccountingError,
    ProductPlanNotFoundError,
)
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.dates import add_months
from django_prbac.models import Role, UserRole


EXCHANGE_RATE_DECIMAL_PLACES = 9


def get_first_last_days(year, month):
    last_day = calendar.monthrange(year, month)[1]
    date_start = datetime.date(year, month, 1)
    date_end = datetime.date(year, month, last_day)
    return date_start, date_end


def get_previous_month_date_range(reference_date=None):
    reference_date = reference_date or datetime.date.today()

    last_month_year, last_month = add_months(reference_date.year, reference_date.month, -1)
    return get_first_last_days(last_month_year, last_month)


def months_from_date(reference_date, months_from_date):
    year, month = add_months(reference_date.year, reference_date.month, months_from_date)
    return datetime.date(year, month, 1)


def ensure_domain_instance(domain):
    if not isinstance(domain, Domain):
        domain = Domain.get_by_name(domain)
    return domain


def fmt_feature_rate_dict(feature, feature_rate=None):
    """
    This will be turned into a JSON representation of this Feature and its FeatureRate
    """
    if feature_rate is None:
        feature_rate = feature.get_rate()
    return {
        'name': feature.name,
        'feature_type': feature.feature_type,
        'feature_id': feature.id,
        'rate_id': feature_rate.id,
        'monthly_fee': feature_rate.monthly_fee.__str__(),
        'monthly_limit': feature_rate.monthly_limit,
        'per_excess_fee': feature_rate.per_excess_fee.__str__(),
    }


def fmt_product_rate_dict(product, product_rate=None):
    """
    This will be turned into a JSON representation of this SoftwareProduct and its SoftwareProductRate
    """
    if product_rate is None:
        product_rate = product.get_rate()
    return {
        'name': product.name,
        'product_type': product.product_type,
        'product_id': product.id,
        'rate_id': product_rate.id,
        'monthly_fee': product_rate.monthly_fee.__str__(),
    }


def get_privileges(plan_version):
    role = plan_version.role.get_cached_role()
    return set([grant.to_role.slug for grant in role.memberships_granted.all()])


def get_change_status(from_plan_version, to_plan_version):
    from_privs = (
        get_privileges(from_plan_version)
        if from_plan_version is not None
        else set(privileges.MAX_PRIVILEGES)
    )
    to_privs = get_privileges(to_plan_version) if to_plan_version is not None else set()

    downgraded_privs = from_privs.difference(to_privs)
    upgraded_privs = to_privs

    from corehq.apps.accounting.models import SubscriptionAdjustmentReason as Reason
    if from_plan_version is None:
        adjustment_reason = Reason.CREATE
    else:
        adjustment_reason = Reason.SWITCH
        if len(downgraded_privs) == 0 and len(upgraded_privs) > 0:
            adjustment_reason = Reason.UPGRADE
        elif len(upgraded_privs) == 0 and len(downgraded_privs) > 0:
            adjustment_reason = Reason.DOWNGRADE
    return adjustment_reason, downgraded_privs, upgraded_privs


def domain_has_privilege_cache_args(domain, privilege_slug, **assignment):
    return [
        domain.name if isinstance(domain, Domain) else domain,
        privilege_slug
    ]


@quickcache(domain_has_privilege_cache_args, timeout=10)
def domain_has_privilege(domain, privilege_slug, **assignment):
    from corehq.apps.accounting.models import Subscription
    try:
        plan_version = Subscription.get_subscribed_plan_by_domain(domain)[0]
        privilege = Role.get_privilege(privilege_slug, assignment)
        if privilege is None:
            return False
        if plan_version.role.has_privilege(privilege):
            return True
    except ProductPlanNotFoundError:
        return False
    except AccountingError:
        pass
    return False


def is_active_subscription(date_start, date_end):
    today = datetime.date.today()
    return ((date_start is None or date_start <= today)
            and (date_end is None or today < date_end))


def has_subscription_already_ended(subscription):
    return (subscription.date_end is not None
            and subscription.date_end <= datetime.date.today())


def get_money_str(amount):
    if amount is not None:
        if amount < 0:
            fmt = "-$%0.2f"
            amount = abs(amount)
        else:
            fmt = "$%0.2f"
        return fmt % amount
    return ""


def get_address_from_invoice(invoice):
    from corehq.apps.accounting.invoice_pdf import Address
    from corehq.apps.accounting.models import BillingContactInfo
    try:
        contact_info = BillingContactInfo.objects.get(
            account=invoice.account,
        )
        return Address(
            name=(
                "%s %s" %
                (contact_info.first_name
                 if contact_info.first_name is not None else "",
                 contact_info.last_name
                 if contact_info.last_name is not None else "")
            ),
            company_name=contact_info.company_name,
            first_line=contact_info.first_line,
            second_line=contact_info.second_line,
            city=contact_info.city,
            region=contact_info.state_province_region,
            postal_code=contact_info.postal_code,
            country=contact_info.country,
        )
    except BillingContactInfo.DoesNotExist:
        return Address()


def get_dimagi_from_email_by_product(product):
    return ("Dimagi %(product)s Accounts <%(email)s>" % {
        'product': product,
        'email': settings.INVOICING_CONTACT_EMAIL,
    })


def quantize_accounting_decimal(decimal_value):
    return decimal_value.quantize(Decimal(10) ** -2)


def fmt_dollar_amount(decimal_value):
    return _("USD %s") % quantize_accounting_decimal(decimal_value)


def get_customer_cards(account, username, domain):
    from corehq.apps.accounting.models import (
        PaymentMethod, PaymentMethodType,
    )
    from corehq.apps.accounting.payment_handlers import get_or_create_stripe_customer
    try:
        payment_method = PaymentMethod.objects.get(
            web_user=username,
            method_type=PaymentMethodType.STRIPE
        )
        stripe_customer = get_or_create_stripe_customer(payment_method)
        return stripe_customer.cards
    except (PaymentMethod.DoesNotExist):
        pass
    return None


def is_accounting_admin(user):
    accounting_privilege = Role.get_privilege(privileges.ACCOUNTING_ADMIN)
    if accounting_privilege is None:
        return False
    try:
        return user.prbac_role.has_privilege(accounting_privilege)
    except (AttributeError, UserRole.DoesNotExist):
        return False


def get_active_reminders_by_domain_name(domain_name):
    from corehq.apps.reminders.models import (
        CaseReminderHandler,
        REMINDER_TYPE_DEFAULT,
        REMINDER_TYPE_KEYWORD_INITIATED,
    )
    db = CaseReminderHandler.get_db()
    key = [domain_name]
    reminder_rules = db.view(
        'reminders/handlers_by_reminder_type',
        startkey=key,
        endkey=(key + [{}]),
        reduce=False
    ).all()
    return [
        CaseReminderHandler.wrap(reminder_doc)
        for reminder_doc in iter_docs(db, [r['id'] for r in reminder_rules])
        if (
            reminder_doc.get('active', True)
            and reminder_doc.get('reminder_type', REMINDER_TYPE_DEFAULT) != REMINDER_TYPE_KEYWORD_INITIATED
        )
    ]


def make_anchor_tag(href, name, attrs={}):
    context = {
        'href': href,
        'name': name,
        'attrs': attrs,
    }
    return render_to_string('accounting/partials/anchor_tag.html', context)
