from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription


def upgrade_subscriptions_to_latest_plan_version(old_plan_version, web_user,
                                                 upgrade_note):
    subscriptions_needing_upgrade = Subscription.visible_objects.filter(
        is_active=True, plan_version=old_plan_version
    )
    new_plan_version = old_plan_version.plan.get_version()
    for subscription in subscriptions_needing_upgrade:
        subscription.upgrade_plan_for_consistency(new_plan_version, upgrade_note, web_user)


def plan_enabled(plan, domain):
    """
    Returns ``True`` if the SoftwarePlanEdition of ``domain`` is at
    ``plan`` or higher, otherwise returns ``False``.
    """
    assert plan in SoftwarePlanEdition.ASCENDING_ORDER, (
        f'Unable to evaluate {plan!r} plan.'
    )

    subs = Subscription.get_active_subscription_by_domain(domain)
    if not subs:
        return False

    domain_plan = subs.plan_version.plan.edition
    domain_index = SoftwarePlanEdition.ASCENDING_ORDER.index(domain_plan)
    index_required = SoftwarePlanEdition.ASCENDING_ORDER.index(plan)
    return domain_index >= index_required
