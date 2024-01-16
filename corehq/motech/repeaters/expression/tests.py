import json
from datetime import datetime, timedelta

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import UCRExpression
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.expression.repeaters import CaseExpressionRepeater
from corehq.motech.repeaters.models import SQLRepeatRecord
from corehq.util.test_utils import flag_enabled


@flag_enabled('EXPRESSION_REPEATER')
class CaseExpressionRepeaterTest(TestCase, DomainSubscriptionMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'test'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(clear_plan_version_cache)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.setup_subscription(cls.domain, SoftwarePlanEdition.PRO)
        cls.addClassCleanup(cls.teardown_subscriptions)

        cls.factory = CaseFactory(cls.domain)

        url = 'fake-url'
        cls.connection = ConnectionSettings.objects.create(domain=cls.domain, name=url, url=url)
        cls.repeater = CaseExpressionRepeater(
            domain=cls.domain,
            connection_settings_id=cls.connection.id,
            configured_filter={
                "type": "or",
                "filters": [
                    {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "reduce_items",
                            "aggregation_fn": "count",
                            "items_expression": {
                                "type": "get_case_forms",
                                "case_id_expression": {
                                    "property_name": "case_id",
                                    "type": "property_name"
                                }
                            }
                        },
                        "operator": "gt",
                        "property_value": 1
                    },
                    {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "property_name",
                            "property_name": "type",
                        },
                        "operator": "eq",
                        "property_value": "forward-me",
                    }
                ]
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
    def repeat_records(cls, domain_name):
        # Enqueued repeat records have next_check set 48 hours in the future.
        later = datetime.utcnow() + timedelta(hours=48 + 1)
        return SQLRepeatRecord.objects.filter(domain=domain_name, next_check__lt=later)

    def test_filter_cases(self):
        forwardable_case = self.factory.create_case(case_type='forward-me')
        unforwardable_case = self.factory.create_case(case_type='dont-forward-me')
        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(SQLRepeatRecord.objects.filter(domain=self.domain).count(), 1)
        self.assertEqual(repeat_records[0].payload_id, forwardable_case.case_id)

        self.factory.update_case(unforwardable_case.case_id, update={'now-this-case': 'can-be-forwarded'})
        repeat_records = self.repeat_records(self.domain).all()
        self.assertEqual(SQLRepeatRecord.objects.filter(domain=self.domain).count(), 2)
        self.assertEqual(repeat_records[1].payload_id, unforwardable_case.case_id)

    def test_payload(self):
        forwardable_case = self.factory.create_case(case_type='forward-me')
        repeat_record = self.repeat_records(self.domain).all()[0]
        self.assertEqual(repeat_record.get_payload(), json.dumps({
            "case_id": forwardable_case.case_id,
            "a-constant": "foo",
        }))

    @flag_enabled("UCR_EXPRESSION_REGISTRY")
    def test_custom_url(self):

        self.repeater.url_template = "/{variable1}/a_thing/delete?case_id={case_id}&{missing_variable}='foo'"

        UCRExpression.objects.create(
            name='variable1',
            domain=self.domain,
            expression_type="named_expression",
            definition={
                "type": "property_name",
                "property_name": "prop1"
            },
        )
        UCRExpression.objects.create(
            name='case_id',
            domain=self.domain,
            expression_type="named_expression",
            definition={
                "type": "property_name",
                "property_name": "case_id"
            },
        )

        forwardable_case = self.factory.create_case(case_type='forward-me', update={'prop1': 'foo'})
        repeat_record = self.repeat_records(self.domain).all()[0]

        expected_url = self.connection.url + f"/foo/a_thing/delete?case_id={forwardable_case.case_id}&='foo'"

        self.assertEqual(
            self.repeater.get_url(repeat_record),
            expected_url
        )
