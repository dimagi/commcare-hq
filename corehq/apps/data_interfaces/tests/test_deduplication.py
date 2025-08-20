from django.test import TestCase

from corehq.apps.data_interfaces.models import CaseDeduplicationActionDefinition, CaseDuplicateNew
from corehq.apps.data_interfaces.tests.deduplication_helpers import create_dedupe_rule
from corehq.apps.data_interfaces.deduplication import reset_deduplicate_rule


class ResetDuplicateRuleTests(TestCase):
    def test_removes_all_existing_entries(self):
        rule = create_dedupe_rule()
        action = CaseDeduplicationActionDefinition.from_rule(rule)
        CaseDuplicateNew.objects.create(case_id='1234', action=action, hash='123')

        reset_deduplicate_rule(rule)

        rules_found = CaseDuplicateNew.objects.filter(action=action)
        self.assertEqual(rules_found.count(), 0)
