import datetime
import logging
from collections import defaultdict, namedtuple

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from django_prbac.models import Grant, Role, UserRole

from corehq.const import USER_DATE_FORMAT
from dimagi.utils.dates import add_months

from corehq import privileges
from corehq.apps.accounting.exceptions import (
    AccountingError,
    ProductPlanNotFoundError,
)
from corehq.apps.domain.models import Domain
from corehq.toggles import domain_has_privilege_from_toggle
from corehq.util.quickcache import quickcache
from corehq.util.view_utils import absolute_reverse

logger = logging.getLogger('accounting')

EXCHANGE_RATE_DECIMAL_PLACES = 9


def log_accounting_error(message, show_stack_trace=False):
    logger.error("[BILLING] %s" % message, exc_info=show_stack_trace)


def log_accounting_info(message):
    logger.info("[BILLING] %s" % message)


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
        'monthly_fee': str(feature_rate.monthly_fee),
        'monthly_limit': feature_rate.monthly_limit,
        'per_excess_fee': str(feature_rate.per_excess_fee),
    }


def fmt_product_rate_dict(product_name, product_rate=None):
    """
    This will be turned into a JSON representation of this SoftwareProductRate
    """
    from corehq.apps.accounting.models import SoftwareProductRate

    if product_rate is None:
        try:
            product_rate = SoftwareProductRate.objects.filter(
                is_active=True,
                name=product_name,
            ).latest('date_created')
        except SoftwareProductRate.DoesNotExist:
            product_rate = SoftwareProductRate.objects.create(name=product_name, is_active=True)
    return {
        'name': product_rate.name,
        'rate_id': product_rate.id,
        'monthly_fee': str(product_rate.monthly_fee),
    }


def get_privileges(plan_version):
    role = plan_version.role.get_cached_role()
    return set([grant.to_role.slug for grant in role.memberships_granted.all()])


ChangeStatusResult = namedtuple('ChangeStatusResult', ['adjustment_reason', 'downgraded_privs', 'upgraded_privs'])


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
    return ChangeStatusResult(adjustment_reason, downgraded_privs, upgraded_privs)


def domain_has_privilege_cache_args(domain, privilege_slug, **assignment):
    return [
        domain.name if isinstance(domain, Domain) else domain,
        privilege_slug
    ]


@quickcache(domain_has_privilege_cache_args, timeout=10)
def domain_has_privilege(domain, privilege_slug, **assignment):
    from corehq.apps.accounting.models import Subscription
    try:
        plan_version = Subscription.get_subscribed_plan_by_domain(domain)
        privilege = Role.get_privilege(privilege_slug, assignment)
        if privilege is None:
            return False
        if plan_version.role.has_privilege(privilege):
            return True
        elif domain_has_privilege_from_toggle(privilege_slug, domain):
            return True
    except ProductPlanNotFoundError:
        return False
    except AccountingError:
        pass
    return False


def get_domains_with_privilege(privilege_slug):
    return [
        domain for domain in Domain.get_all_names()
        if domain_has_privilege(domain, privilege_slug.slug)
    ]


@quickcache(['domain_name'], timeout=15 * 60)
def domain_is_on_trial(domain_name):
    from corehq.apps.accounting.models import Subscription
    subscription = Subscription.get_active_subscription_by_domain(domain_name)
    return subscription and subscription.is_trial


def is_active_subscription(date_start, date_end, today=None):
    today = today or datetime.date.today()
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


def get_dimagi_from_email():
    return ("Dimagi CommCare Accounts <%(email)s>" % {
        'email': settings.INVOICING_CONTACT_EMAIL,
    })


def quantize_accounting_decimal(decimal_value):
    return "%0.2f" % decimal_value


def fmt_dollar_amount(decimal_value):
    return _("USD %s") % quantize_accounting_decimal(decimal_value)


def is_accounting_admin(user):
    accounting_privilege = Role.get_privilege(privileges.ACCOUNTING_ADMIN)
    if accounting_privilege is None:
        return False
    try:
        return user.prbac_role.has_privilege(accounting_privilege)
    except (AttributeError, UserRole.DoesNotExist):
        return False


def make_anchor_tag(href, name, attrs=None):
    context = {
        'href': href,
        'name': name,
        'attrs': attrs or {},
    }
    return render_to_string('accounting/partials/anchor_tag.html', context)


def get_default_domain_url(domain):
    from corehq.apps.domain.views.settings import DefaultProjectSettingsView
    return absolute_reverse(
        DefaultProjectSettingsView.urlname,
        args=[domain],
    )


def get_all_roles_by_slug():
    return {role.slug: role for role in Role.objects.all()}


def get_granted_privs_for_grantee():
    """
    Builds a dictionary where each grantee_slug contains a set of privilege slugs that have been granted
    :return: {<grantee_slug>: {<priv_slug>, <priv_slug>}, ... }
    """
    granted_privs_for_grantee = defaultdict(set)
    for grant in Grant.objects.select_related('from_role', 'to_role').all():
        granted_privs_for_grantee[grant.from_role.slug].add(grant.to_role.slug)

    return granted_privs_for_grantee


def ensure_grants(privs_to_ensure_for_grantee, dry_run=False, verbose=False, roles_by_slug=None):
    """
    Adds a parameterless grant between grantee and priv, looked up by slug.
    :param privs_to_ensure_for_grantee: An iterable of tuples: `(grantee_slug, [priv_slugs])`
    :param dry_run: if True, will not make any changes to the DB
    :param verbose: if True, will log additional output
    :param roles_by_slug: can specify your own roles to consider, otherwise will fetch all Role objects
    """
    dry_run_tag = "[DRY RUN] " if dry_run else ""
    roles_by_slug = roles_by_slug or get_all_roles_by_slug()
    granted_privs_for_grantee = get_granted_privs_for_grantee()

    grants_to_create = []
    for grantee_slug, priv_slugs in privs_to_ensure_for_grantee:
        if grantee_slug not in roles_by_slug:
            logger.info('grantee %s does not exist.', grantee_slug)
            continue

        for priv_slug in priv_slugs:
            if priv_slug not in roles_by_slug:
                logger.info('privilege %s does not exist.', priv_slug)
                continue

            if priv_slug in granted_privs_for_grantee[grantee_slug]:
                if verbose or dry_run:
                    logger.info('%sPrivilege already granted: %s => %s',
                        dry_run_tag, grantee_slug, priv_slug)
            else:
                granted_privs_for_grantee[grantee_slug].add(priv_slug)
                if verbose or dry_run:
                    logger.info('%sGranting privilege: %s => %s',
                        dry_run_tag, grantee_slug, priv_slug)
                if not dry_run:
                    grants_to_create.append(Grant(
                        from_role=roles_by_slug[grantee_slug],
                        to_role=roles_by_slug[priv_slug]
                    ))
    if grants_to_create:
        Role.get_cache().clear()
        Grant.objects.bulk_create(grants_to_create)


def revoke_privs_for_grantees(privs_for_grantees, dry_run=False, verbose=False):
    """
    Removes existing grants between grantee roles and privilege roles, looked up by slug.
    :param privs_for_grantees: An iterable of tuples: `(grantee_slug, [priv_slugs])`
    :param dry_run: if True, will not make any changes to the DB
    :param verbose: if True, will log additional output
    """
    dry_run_tag = "[DRY RUN] " if dry_run else ""
    roles_by_slug = get_all_roles_by_slug()

    grants_to_delete = []
    for grantee_slug, priv_slugs in privs_for_grantees:
        if grantee_slug not in roles_by_slug:
            logger.info(f'grantee {grantee_slug} does not exist.')
            continue

        for priv_slug in priv_slugs:
            if priv_slug not in roles_by_slug:
                logger.info(f'privilege {priv_slug} does not exist.')
                continue

            existing_grants = get_grants(roles_by_slug[grantee_slug], roles_by_slug[priv_slug])
            if existing_grants:
                if verbose or dry_run:
                    logger.info(f'{dry_run_tag}Revoking privilege: {grantee_slug} => {priv_slug}')
                if not dry_run:
                    grants_to_delete.extend(existing_grants)
            else:
                if verbose or dry_run:
                    logger.info(f'{dry_run_tag}Privilege already revoked: {grantee_slug} => {priv_slug}')

    if grants_to_delete:
        delete_grants(grants_to_delete)


def get_grants(from_role, to_role):
    return Grant.objects.filter(
        from_role=from_role,
        to_role=to_role
    )


def delete_grants(grants):
    Role.get_cache().clear()
    for grant in grants:
        grant.delete()


def log_removed_grants(priv_slugs, dry_run=False):
    grants = Grant.objects.filter(to_role__slug__in=list(priv_slugs))
    if grants:
        logger.info("%sRemoving privileges: %s",
            ("[DRY RUN] " if dry_run else ""),
            ", ".join(g.to_role.slug for g in grants),
        )


def get_account_name_from_default_name(default_name):
    from corehq.apps.accounting.models import BillingAccount
    if not BillingAccount.objects.filter(name=default_name).exists():
        return default_name
    else:
        matching_regex_count = BillingAccount.objects.filter(
            name__iregex=r'^%s \(\d+\)$' % default_name,
        ).count()
        return '%s (%d)' % (
            default_name,
            matching_regex_count + 1
        )


def cancel_future_subscriptions(domain_name, from_date, web_user):
    from corehq.apps.accounting.models import (
        Subscription,
        SubscriptionAdjustment,
        SubscriptionAdjustmentReason,
    )
    for later_subscription in Subscription.visible_objects.filter(
        subscriber__domain=domain_name,
        date_start__gt=from_date,
    ).order_by('date_start').all():
        later_subscription.date_end = later_subscription.date_start
        later_subscription.save()
        SubscriptionAdjustment.record_adjustment(
            later_subscription,
            reason=SubscriptionAdjustmentReason.CANCEL,
            web_user=web_user,
            note="Cancelled due to changing subscription",
        )


def pause_current_subscription(domain_name, web_user, current_subscription):
    from corehq.apps.accounting.models import (
        Subscription,
        DefaultProductPlan,
        SoftwarePlanEdition,
        SubscriptionAdjustmentMethod,
        SubscriptionType,
        ProBonoStatus,
        FundingSource,
    )
    cancel_future_subscriptions(domain_name, datetime.date.today(), web_user)
    paused_plan_version = DefaultProductPlan.get_default_plan_version(
        SoftwarePlanEdition.PAUSED
    )
    if current_subscription.is_below_minimum_subscription:
        current_subscription.update_subscription(
            date_start=current_subscription.date_start,
            date_end=current_subscription.date_start + datetime.timedelta(days=30)
        )
        return Subscription.new_domain_subscription(
            account=current_subscription.account,
            domain=domain_name,
            plan_version=paused_plan_version,
            date_start=current_subscription.date_start + datetime.timedelta(days=30),
            web_user=web_user,
            adjustment_method=SubscriptionAdjustmentMethod.USER,
            service_type=SubscriptionType.PRODUCT,
            pro_bono_status=ProBonoStatus.NO,
            funding_source=FundingSource.CLIENT,
            do_not_invoice=True,
            no_invoice_reason='Paused plan',
        )
    else:
        return current_subscription.change_plan(
            paused_plan_version,
            web_user=web_user,
            adjustment_method=SubscriptionAdjustmentMethod.USER,
            service_type=SubscriptionType.PRODUCT,
            pro_bono_status=ProBonoStatus.NO,
            do_not_invoice=True,
            no_invoice_reason='Paused plan',
        )


def is_downgrade(current_edition, next_edition):
    from corehq.apps.accounting.models import SoftwarePlanEdition
    plans = SoftwarePlanEdition.SELF_SERVICE_ORDER + [SoftwarePlanEdition.ENTERPRISE]
    return plans.index(current_edition) > plans.index(next_edition)


def clear_plan_version_cache():
    from corehq.apps.accounting.models import SoftwarePlan
    for software_plan in SoftwarePlan.objects.all():
        SoftwarePlan.get_version.clear(software_plan)


def get_paused_plan_context(request, domain):
    from corehq.apps.accounting.models import Subscription
    from corehq.apps.domain.views import SelectPlanView

    current_sub = Subscription.get_active_subscription_by_domain(domain)
    if (not current_sub
            or not current_sub.plan_version.is_paused
            or not current_sub.previous_subscription):
        return {}

    previous_edition = (current_sub.previous_subscription.plan_version.plan.edition
                        if current_sub.previous_subscription else "")
    return {
        'is_trial': current_sub.previous_subscription.is_trial,
        'is_paused': True,
        'previous_edition': previous_edition,
        'paused_date': current_sub.date_start.strftime(USER_DATE_FORMAT),
        'change_plan_url': reverse(SelectPlanView.urlname, args=[domain]),
        'can_edit_billing_info': request.couch_user.is_domain_admin(domain),
    }
