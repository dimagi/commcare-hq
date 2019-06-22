from __future__ import absolute_import, division
from __future__ import unicode_literals
from corehq import toggles
from dimagi.utils.couch.cache.cache_core import get_redis_client
from django.conf import settings


class MessagingRuleProgressHelper(object):

    def __init__(self, rule_id):
        self.rule_id = rule_id
        self.client = get_redis_client()

    @property
    def key_expiry(self):
        return 48 * 60 * 60

    @property
    def current_key(self):
        return 'messaging-rule-case-count-current-%s' % self.rule_id

    @property
    def total_key(self):
        return 'messaging-rule-case-count-total-%s' % self.rule_id

    @property
    def rule_initiation_key(self):
        return 'messaging-rule-run-initiated-%s' % self.rule_id

    def set_rule_initiation_key(self):
        self.client.set(self.rule_initiation_key, 1, timeout=2 * 60 * 60)

    def clear_rule_initiation_key(self):
        self.client.delete(self.rule_initiation_key)

    def rule_initiation_key_is_set(self):
        return self.client.get(self.rule_initiation_key) is not None

    def rule_initiation_key_minutes_remaining(self):
        return (self.client.ttl(self.rule_initiation_key) // 60) or 1

    def set_initial_progress(self):
        self.client.set(self.current_key, 0)
        self.client.set(self.total_key, 0)
        self.client.expire(self.current_key, self.key_expiry)
        self.client.expire(self.total_key, self.key_expiry)
        self.set_rule_initiation_key()

    def set_rule_complete(self):
        self.clear_rule_initiation_key()

    def increment_current_case_count(self, fail_hard=False):
        try:
            self.client.incr(self.current_key)
        except:
            if fail_hard:
                raise

    def increase_total_case_count(self, value):
        self.client.incr(self.total_key, delta=value)
        self.client.expire(self.total_key, self.key_expiry)

    @staticmethod
    def _int_or_zero(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def get_progress_pct(self):
        current = self._int_or_zero(self.client.get(self.current_key))
        total = self._int_or_zero(self.client.get(self.total_key))

        if not current or not total:
            return 0

        if current >= total:
            return 100

        return int(round(100.0 * current / total, 0))


def use_phone_entries():
    """
    Phone entries are not used in ICDS because they're not needed and
    it helps performance to avoid keeping them up to date.
    """
    return settings.SERVER_ENVIRONMENT not in settings.ICDS_ENVS


def show_messaging_dashboard(domain, couch_user):
    return (
        not toggles.HIDE_MESSAGING_DASHBOARD_FROM_NON_SUPERUSERS.enabled(domain) or
        couch_user.is_superuser
    )
