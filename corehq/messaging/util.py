from dimagi.utils.couch.cache.cache_core import get_redis_client


class MessagingRuleProgressHelper(object):

    def __init__(self, rule_id):
        self.rule_id = rule_id
        self.client = get_redis_client()

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
        self.client.expire(self.current_key, 48 * 60 * 60)
        self.client.expire(self.total_key, 48 * 60 * 60)
        self.client.expire(self.in_progress_key, 48 * 60 * 60)

    def set_rule_complete(self):
        self.client.set(self.in_progress_key, 0)

    def increment_current_case_count(self):
        self.client.incr(self.current_key)

    def set_total_case_count(self, value):
        self.client.set(self.total_key, value)
