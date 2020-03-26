from corehq.apps.accounting.models import SoftwarePlanEdition


def is_subscription_eligible_for_downgrade_process(subscription):
    return (
        subscription.plan_version.plan.edition not in [
            SoftwarePlanEdition.COMMUNITY,
            SoftwarePlanEdition.PAUSED,
        ] and not subscription.skip_auto_downgrade
    )
