import uuid
import datetime

from django.test import TestCase
from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.userreports.models import DataSourceConfiguration


class ChildHealthExpressionTest(TestCase):
    """
    Integration tests for data-source configs that use the custom-expression
    'custom.icds.ucr.expressions.child_health_property'
    """
    def setUp(self):
        self.config = DataSourceConfiguration(
            domain='test',
            display_name='foo',
            referenced_doc_type='CommCareCase',
            table_id="ding",
            base_item_expression={
                'type': 'iterator',
                'expressions': [-3, -2, -1, 0, 1, 2, 3]
            },
            configured_filter={
                u'operator': u'eq',
                u'type': u'boolean_expression',
                u'expression': {
                    u'type': u'property_name',
                    u'property_name': u'type'
                },
                u'property_value': 'child'
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "column_id": "age_in_months",
                    "datatype": "integer",
                    "expression": {
                        'type': 'child_health_property',
                        'indicator_name': 'age_in_months',
                        'start_date': {
                            'type': 'named',
                            'name': 'iteration_start_date'
                        },
                        'end_date': {
                            'type': 'named',
                            'name': 'iteration_end_date'
                        }
                    }
                },
                {
                    "type": "expression",
                    "column_id": "start_date",
                    "datatype": "date",
                    "expression": {
                        "type": 'named',
                        'name': 'iteration_start_date'
                    }
                },
                {
                    "type": "expression",
                    "column_id": "end_date",
                    "datatype": "date",
                    "expression": {
                        "type": 'named',
                        'name': 'iteration_end_date'
                    }
                },
            ],
            named_expressions={
                'iteration_start_date': {
                    'type': 'add_months',
                    'date_expression': {
                        'type': 'month_start_date',
                        'date_expression': {
                            'type': 'root_doc',
                            'expression': {
                                'type': 'property_name',
                                'property_name': 'received_on'
                            }
                        }
                    },
                    'months_expression': {
                        'type': 'identity'
                    }
                },
                'iteration_end_date': {
                    'type': 'add_months',
                    'date_expression': {
                        'type': 'month_end_date',
                        'date_expression': {
                            'type': 'root_doc',
                            'expression': {
                                'type': 'property_name',
                                'property_name': 'received_on'
                            }
                        }
                    },
                    'months_expression': {
                        'type': 'identity'
                    }
                }
            },
        )

    def tearDown(self):
        delete_all_cases()

    def test_expression(self):
        factory = CaseFactory(domain='test')

        child_case_id = uuid.uuid4().hex
        person_case_id = uuid.uuid4().hex
        structures = [
            CaseStructure(
                case_id=child_case_id,
                attrs={
                    'case_type': 'child',
                    'update': {'received_on': '2016-03-22'},
                },
                indices=[
                    CaseIndex(
                        CaseStructure(
                            case_id=person_case_id,
                            attrs={
                                'update': {'dob': '2016-02-22'},
                                'case_type': 'person'
                            }
                        )
                    )
                ],
            )
        ]

        [child_case, person_case] = factory.create_or_update_cases(structures)
        rows = self.config.get_all_values(child_case.to_json())

        self.assertEqual(len(rows), 7)

        expected_rows = [
            (1, datetime.date(2015, 12, 1), datetime.date(2015, 12, 31)),
            (0, datetime.date(2016, 1, 1), datetime.date(2016, 1, 31)),
            (0, datetime.date(2016, 2, 1), datetime.date(2016, 2, 29)),
            (-1, datetime.date(2016, 3, 1), datetime.date(2016, 3, 31)),
            (-2, datetime.date(2016, 4, 1), datetime.date(2016, 4, 30)),
            (-3, datetime.date(2016, 5, 1), datetime.date(2016, 5, 31)),
            (-4, datetime.date(2016, 6, 1), datetime.date(2016, 6, 30))
        ]
        actual_rows = [(row[3].value, row[4].value, row[5].value) for row in rows]

        self.assertEqual(actual_rows, expected_rows)
