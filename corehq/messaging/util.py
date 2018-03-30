from __future__ import absolute_import, division
from __future__ import unicode_literals
from dimagi.utils.couch.cache.cache_core import get_redis_client


class MessagingRuleProgressHelper(object):

    def __init__(self, rule_id):
        self.rule_id = rule_id
        self.client = get_redis_client()

    @property
    def key_expiry(self):
        return 48 * 60 * 60

    @property
    def in_progress_key(self):
        return 'messaging-rule-processing-in-progress-%s' % self.rule_id

    @property
    def current_key(self):
        return 'messaging-rule-case-count-current-%s' % self.rule_id

    @property
    def total_key(self):
        return 'messaging-rule-case-count-total-%s' % self.rule_id

    def set_initial_progress(self):
        self.client.set(self.current_key, 0)
        self.client.set(self.total_key, 0)
        self.client.set(self.in_progress_key, 1)
        self.client.expire(self.current_key, self.key_expiry)
        self.client.expire(self.total_key, self.key_expiry)
        self.client.expire(self.in_progress_key, self.key_expiry)

    def set_rule_complete(self):
        self.client.set(self.in_progress_key, 0)

    def increment_current_case_count(self, fail_hard=False):
        try:
            self.client.incr(self.current_key)
        except:
            if fail_hard:
                raise

    def set_total_case_count(self, value):
        self.client.set(self.total_key, value)
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
