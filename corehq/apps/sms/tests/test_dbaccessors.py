from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.sms.dbaccessors import get_forwarding_rules_for_domain
from corehq.apps.sms.models import ForwardingRule


class DBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        cls.domain = 'forwarding-rules-dbaccessors'
        cls.forwarding_rules = [
            ForwardingRule(domain=cls.domain),
            ForwardingRule(domain=cls.domain),
            ForwardingRule(domain='other'),
        ]
        ForwardingRule.get_db().bulk_save(cls.forwarding_rules)

    @classmethod
    def tearDownClass(cls):
        ForwardingRule.get_db().bulk_delete(cls.forwarding_rules)
        super(DBAccessorsTest, cls).tearDownClass()

    def test_get_forwarding_rules_for_domain(self):
        self.assertItemsEqual(
            [rule.to_json()
             for rule in get_forwarding_rules_for_domain(self.domain)],
            [rule.to_json() for rule in self.forwarding_rules
             if rule.domain == self.domain]
        )
