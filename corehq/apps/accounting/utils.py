import calendar
import datetime
import json
from django.utils.encoding import force_unicode
from django.utils.functional import Promise
from corehq import Domain, privileges
from corehq.apps.accounting.exceptions import AccountingError
from dimagi.utils.dates import add_months
from django_prbac.models import Role


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
    role = plan_version.role
    return set([grant.to_role.slug for grant in role.memberships_granted.all()])


def get_change_status(from_plan_version, to_plan_version):
    all_privs = set(privileges.MAX_PRIVILEGES)
    from_privs = get_privileges(from_plan_version) if from_plan_version is not None else all_privs
    to_privs = get_privileges(to_plan_version)

    downgraded_privs = all_privs.difference(to_privs)
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


def domain_has_privilege(domain, privilege_slug, **assignment):
    from corehq.apps.accounting.models import Subscription
    try:
        plan_version = Subscription.get_subscribed_plan_by_domain(domain)[0]
        roles = Role.objects.filter(slug=privilege_slug)
        if not roles:
            return False
        privilege = roles[0].instantiate(assignment)
        if plan_version.role.has_privilege(privilege):
            return True
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
