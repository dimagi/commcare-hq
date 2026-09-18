"""Subscription-based monthly allowances for the OCS chat widget."""

from django.conf import settings

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription


UNLIMITED = -1
CHATBOT_MESSAGE_QUOTA_BY_EDITION = {
    SoftwarePlanEdition.FREE: 0,
    SoftwarePlanEdition.STANDARD: 30,
    SoftwarePlanEdition.PRO: 30,
    SoftwarePlanEdition.ADVANCED: 60,
    SoftwarePlanEdition.ENTERPRISE: 60,
}
_MAX_CHATBOT_MESSAGE_QUOTA = max(CHATBOT_MESSAGE_QUOTA_BY_EDITION.values())


def get_chatbot_message_quota(couch_user):
    if settings.ENTERPRISE_MODE or couch_user.is_dimagi:
        return UNLIMITED

    quota = 0
    for domain in couch_user.get_domains():
        quota = max(quota, CHATBOT_MESSAGE_QUOTA_BY_EDITION.get(_get_domain_edition(domain), 0))
        if quota >= _MAX_CHATBOT_MESSAGE_QUOTA:
            return quota
    return quota


def _get_domain_edition(domain):
    subscription = Subscription.get_active_subscription_by_domain(domain)
    if subscription is None:
        return SoftwarePlanEdition.FREE
    return subscription.plan_version.plan.edition
