import uuid
from datetime import datetime
from django.test import TestCase
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext
from corehq.form_processor.tests.utils import run_with_all_backends
from casexml.apps.case.mock import CaseStructure, CaseFactory, CaseIndex
from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms


class GetChildCasesExpressionTest(TestCase):

    def setUp(self):
        super(GetChildCasesExpressionTest, self).setUp()
        self.domain = uuid.uuid4().hex
        factory = CaseFactory(domain=self.domain)
        self.test_case_id = uuid.uuid4().hex
        parent_case = CaseStructure(
            case_id='p-' + self.test_case_id,
            attrs={
                'case_type': 'parent_case',
                'create': True,
                'date_opened': datetime(2015, 1, 10),
                'date_modified': datetime(2015, 3, 10),
            },
        )
        test_case = CaseStructure(
            case_id=self.test_case_id,
            attrs={
                'case_type': 'test',
                'create': True,
                'date_opened': datetime(2015, 1, 10),
                'date_modified': datetime(2015, 3, 10),
            },
            indices=[CaseIndex(
                parent_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=parent_case.attrs['case_type'],
            )],
        )
        child_case_1 = CaseStructure(
            case_id='c1-' + self.test_case_id,
            attrs={
                'case_type': 'child_1',
                'create': True,
                'date_opened': datetime(2015, 1, 10),
                'date_modified': datetime(2015, 3, 10),
            },
            indices=[CaseIndex(
                test_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=test_case.attrs['case_type'],
            )],
        )
        child_case_2 = CaseStructure(
            case_id='c2-' + self.test_case_id,
            attrs={
                'case_type': 'child_2',
                'create': True,
                'date_opened': datetime(2015, 1, 10),
                'date_modified': datetime(2015, 3, 10),
            },
            indices=[CaseIndex(
                test_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=test_case.attrs['case_type'],
            )],
        )
        factory.create_or_update_cases([parent_case, test_case, child_case_1, child_case_2])

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        super(GetChildCasesExpressionTest, self).tearDown()

    @run_with_all_backends
    def test_all_child_cases(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "icds_get_child_cases",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                }
            }
        })
        self.assertEqual(2, expression({"some_field", "some_value"}, context))

    @run_with_all_backends
    def test_no_child_cases(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "icds_get_child_cases",
                "case_id_expression": {
                    "type": "constant",
                    "constant": "c1-" + self.test_case_id
                }
            }
        })
        self.assertEqual(0, expression({"some_field", "some_value"}, context))

    @run_with_all_backends
    def test_filtered_child_cases(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "filter_items",
                "filter_expression": {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_name",
                        "property_name": "type"
                    },
                    "property_value": "child_1"
                },
                "items_expression": {
                    "type": "icds_get_child_cases",
                    "case_id_expression": {
                        "type": "constant",
                        "constant": self.test_case_id
                    }
                }
            }
        })
        self.assertEqual(1, expression({"some_field", "some_value"}, context))
