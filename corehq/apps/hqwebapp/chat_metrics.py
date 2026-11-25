from datetime import datetime

from corehq.apps.domain.models import ChatbotDomainUsage
from corehq.apps.hqwebapp.models import ChatbotQuotaPressure

QUOTA_WARNING_SHARE = 0.8


def record_chatbot_message(domain, couch_user, quota_limit, quota_used):
    if couch_user.is_dimagi:
        return
    now = datetime.utcnow()
    ChatbotDomainUsage.objects.update_or_create(
        domain=domain,
        user_id=couch_user.user_id,
        defaults={'last_message_at': now},
    )
    quota_updates = _quota_pressure_updates(quota_limit, quota_used, now)
    if quota_updates:
        ChatbotQuotaPressure.objects.update_or_create(user_id=couch_user.user_id, defaults=quota_updates)


def _quota_pressure_updates(quota_limit, quota_used, now):
    if quota_used is None:
        return {}
    updates = {}
    if quota_used >= quota_limit * QUOTA_WARNING_SHARE:
        updates['last_quota_warning_at'] = now
    if quota_used >= quota_limit:
        updates['last_quota_limit_at'] = now
    return updates
