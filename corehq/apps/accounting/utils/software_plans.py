from corehq.apps.accounting.models import Subscription


def upgrade_subscriptions_to_latest_plan_version(old_plan_version, web_user,
                                                 upgrade_note):
    subscriptions_needing_upgrade = Subscription.visible_objects.filter(
        is_active=True, plan_version=old_plan_version
    )
    new_plan_version = old_plan_version.plan.get_version()
    for subscription in subscriptions_needing_upgrade:
        subscription.upgrade_plan_for_consistency(new_plan_version, upgrade_note, web_user)
