from django.db.models import Q
from django.http import Http404
from django_prbac.utils import has_privilege

from corehq import privileges
from corehq.apps.accounting.models import (
    Subscription,
    SoftwarePlanEdition,
    BillingAccount,
    EntryPoint,
    DefaultProductPlan,
    SubscriptionType,
)


def get_account_or_404(request, domain):
    account = BillingAccount.get_account_by_domain(domain)

    if account is None:
        raise Http404()

    if not account.has_enterprise_admin(request.couch_user.username):
        if not has_privilege(request, privileges.ACCOUNTING_ADMIN):
            raise Http404()

    return account


def assign_explicit_unpaid_subscription(domain_name, start_date, method, account=None,
                                        web_user=None, is_paused=False):
    plan_edition = SoftwarePlanEdition.PAUSED if is_paused else SoftwarePlanEdition.COMMUNITY
    future_subscriptions = Subscription.visible_objects.filter(
        date_start__gt=start_date,
        subscriber__domain=domain_name,
    )
    if future_subscriptions.exists():
        end_date = future_subscriptions.earliest('date_start').date_start
    else:
        end_date = None

    if account is None:
        account = BillingAccount.get_or_create_account_by_domain(
            domain_name,
            created_by='assign_explicit_unpaid_subscription',
            entry_point=EntryPoint.SELF_STARTED,
        )[0]

    return Subscription.new_domain_subscription(
        account=account,
        domain=domain_name,
        plan_version=DefaultProductPlan.get_default_plan_version(
            edition=plan_edition
        ),
        date_start=start_date,
        date_end=end_date,
        skip_invoicing_if_no_feature_charges=True,
        adjustment_method=method,
        internal_change=True,
        service_type=SubscriptionType.PRODUCT,
        web_user=web_user,
    )


def ensure_community_or_paused_subscription(domain_name, from_date, method, web_user=None):
    if Subscription.visible_objects.filter(
        Q(date_end__gt=from_date) | Q(date_end__isnull=True),
        date_start__lte=from_date,
        subscriber__domain=domain_name,
    ).exists():
        return

    # if there are any subscriptions present that are not the community edition,
    # then the ensured plan must be PAUSED
    is_paused = Subscription.visible_objects.filter(
        subscriber__domain=domain_name,
    ).exclude(
        plan_version__plan__edition=SoftwarePlanEdition.COMMUNITY
    ).exists()

    assign_explicit_unpaid_subscription(domain_name, from_date, method,
                                        web_user=web_user, is_paused=is_paused)
