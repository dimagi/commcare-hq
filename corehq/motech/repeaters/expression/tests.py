import json
from datetime import datetime, timedelta

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import delete_all_repeat_records
from corehq.motech.repeaters.expression.repeaters import CaseExpressionRepeater
from corehq.motech.repeaters.models import RepeatRecord
from corehq.util.test_utils import flag_enabled


@flag_enabled('EXPRESSION_REPEATER')
class CaseExpressionRepeaterTest(TestCase, DomainSubscriptionMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'test'
        cls.domain_obj = create_domain(cls.domain)
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)

        cls.factory = CaseFactory(cls.domain)

        url = 'fake-url'
        cls.connection = ConnectionSettings.objects.create(domain=cls.domain, name=url, url=url)
        cls.repeater = CaseExpressionRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connection.id,
            configured_filter={
                "type": "boolean_expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "type",
                },
                "operator": "eq",
                "property_value": "forward-me",
            },
            configured_expression={
                "type": "dict",
                "properties": {
                    "case_id": {
                        "type": "property_name",
                        "property_name": "case_id",
                    },
                    "a-constant": {
                        "type": "constant",
                        "constant": "foo",
                    }
                }
            }
        )

        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.repeater.delete()
        cls.connection.delete()
        cls.teardown_subscriptions()
        cls.domain_obj.delete()
        clear_plan_version_cache()
        super().tearDownClass()

    def tearDown(self):
        delete_all_repeat_records()

    @classmethod
    def repeat_records(cls, domain_name):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return RepeatRecord.all(domain=domain_name, due_before=later)

    def test_filter_cases(self):
        forwardable_case = self.factory.create_case(case_type='forward-me')
        unforwardable_case = self.factory.create_case(case_type='dont-forward-me')  # noqa
        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(RepeatRecord.count(domain=self.domain), 1)
        self.assertEqual(repeat_records[0].payload_id, forwardable_case.case_id)

    def test_payload(self):
        forwardable_case = self.factory.create_case(case_type='forward-me')
        repeat_record = self.repeat_records(self.domain).all()[0]
        self.assertEqual(repeat_record.get_payload(), json.dumps({
            "case_id": forwardable_case.case_id,
            "a-constant": "foo",
        }))
