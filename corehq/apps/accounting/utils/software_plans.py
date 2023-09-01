from corehq.apps.accounting.models import Subscription
from corehq.apps.accounting.utils import log_accounting_info


def upgrade_subscriptions_to_latest_plan_version(old_plan_version, web_user,
                                                 upgrade_note):
    subscriptions_needing_upgrade = Subscription.visible_objects.filter(
        is_active=True, plan_version=old_plan_version
    )
    new_plan_version = old_plan_version.plan.get_version()
    for subscription in subscriptions_needing_upgrade:
        try:
            subscription.upgrade_plan_to_main_billing_plan(new_plan_version, upgrade_note, web_user)
        except AssertionError:
            # Assertions will fail if subscription is trial or not type PRODUCT/IMPLEMENTATION
            log_accounting_info(
                f"Skipped upgrading subscription for domain {subscription.subscriber.domain}"
                " due to it is trial or not of type product/implementation."
            )
