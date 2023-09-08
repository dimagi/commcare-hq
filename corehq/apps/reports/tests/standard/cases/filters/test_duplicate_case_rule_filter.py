from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.reports.standard.cases.filters import DuplicateCaseRuleFilter


class TestDuplicateCaseRuleFilter(TestCase):
    def test_get_value_returns_rule(self):
        dedupe_rule = self._create_rule(domain='domain')
        request = self._create_request_for_rule(dedupe_rule)

        value = DuplicateCaseRuleFilter.get_value(request, domain='domain')
        self.assertEqual(value, str(dedupe_rule.id))

    def test_get_value_returns_none_on_data_from_other_domain(self):
        unauthorized_rule = self._create_rule(domain='unauthorized-domain')
        request = self._create_request_for_rule(unauthorized_rule)

        self.assertIsNone(DuplicateCaseRuleFilter.get_value(request, domain='domain'))

    def setUp(self):
        self.factory = RequestFactory()

    def _create_rule(self, domain):
        return AutomaticUpdateRule.objects.create(
            domain=domain,
            name='test-rule',
            case_type='test-case-type',
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
            active=True
        )

    def _create_request_for_rule(self, rule):
        return self.factory.get('dedupe_report_url', data={'duplicate_case_rule': rule.id})
