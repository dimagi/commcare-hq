from corehq.apps.accounting.models import Subscription


def upgrade_subscriptions_to_latest_plan_version(old_plan_version, web_user,
                                                 date_start, upgrade_note):
    subscriptions_needing_upgrade = Subscription.visible_objects.filter(
        is_active=True, plan_version=old_plan_version
    )
    new_plan_version = old_plan_version.plan.get_version()
    for subscription in subscriptions_needing_upgrade:
        subscription.change_plan(
            new_plan_version,
            note=upgrade_note,
            date_end=date_start,
            web_user=web_user,
            service_type=subscription.service_type,
            pro_bono_status=subscription.pro_bono_status,
            funding_source=subscription.funding_source,
            internal_change=True,
        )
