from __future__ import absolute_import
import uuid
from xml.etree import cElementTree as ElementTree
from datetime import date, datetime
from django.test import SimpleTestCase, TestCase
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext
from corehq.apps.receiverwrapper.util import submit_form_locally
from casexml.apps.case.mock import CaseStructure, CaseFactory
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms


def _create_element_with_value(element_name, value):
    if value is None:
        input_value = ''
    try:
        input_value = str(value)
    except Exception:
        input_value = ''

    elem = ElementTree.Element(element_name)
    elem.text = input_value
    return elem


class DiffCalendarMonthsExpressionTest(SimpleTestCase):
    def test_cases(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_diff_calendar_months",
            "from_date_expression": {
                "type": "property_name",
                "property_name": "from",
            },
            "to_date_expression": {
                "type": "property_name",
                "property_name": "to",
            },
        })
        self.assertEqual(0, expression({"from": "2015-06-03", "to": "2015-06-06"}))
        self.assertEqual(1, expression({"from": "2015-06-29", "to": "2015-07-01"}))
        self.assertEqual(12, expression({"from": "2015-06-29", "to": "2016-06-06"}))
        self.assertEqual(11, expression({"from": "2015-06-29", "to": "2016-05-01"}))
        self.assertEqual(15, expression({"from": "2015-06-29", "to": "2016-09-06"}))
        self.assertEqual(-2, expression({"from": "2015-08-29", "to": "2015-06-06"}))


class RootPropertyNameExpressionTest(SimpleTestCase):
    def test_no_datatype(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_root_property_name",
            "property_name": "foo",
        })
        self.assertEqual(
            "foo_value",
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"foo": "foo_value"}, 0)
            )
        )

    def test_datatype(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_root_property_name",
            "property_name": "foo",
            "datatype": "integer",
        })
        self.assertEqual(
            5,
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"foo": "5"}, 0)
            )
        )


class IterateFromOpenedDateExpressionTest(SimpleTestCase):
    def test_not_closed(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_iterate_from_opened_date",
        })
        self.assertEqual(
            [0, 1, 2, 3, 4, 5, 6, 7, 8],
            expression(
                {
                    "opened_on": "2015-06-03T01:10:15.241903Z",
                    "modified_on": "2015-11-10T01:10:15.241903Z",
                    "closed": False
                }
            )
        )

    def test_closed(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_iterate_from_opened_date",
        })
        self.assertEqual(
            [0, 1, 2, 3, 4, 5],
            expression(
                {
                    "opened_on": "2015-06-03T01:10:15.241903Z",
                    "modified_on": "2015-11-10T01:10:15.241903Z",
                    "closed": True,
                    "closed_on": "2015-11-10T01:10:15.241903Z",
                }
            )
        )


class MonthExpressionsTest(SimpleTestCase):
    def test_month_start_date(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_month_start",
        })
        self.assertEqual(
            date(2015, 7, 1),
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"opened_on": "2015-06-03T01:10:15.241903Z", }, 1),
            )
        )

    def test_month_end_date(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_month_end",
        })
        self.assertEqual(
            date(2015, 7, 31),
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"opened_on": "2015-06-03T01:10:15.241903Z", }, 1),
            )
        )


class ParentIdExpressionTest(SimpleTestCase):
    def test_has_parent_id(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_parent_id",
        })
        self.assertEqual(
            "p_id",
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext(
                    {
                        "indices": [
                            {
                                "identifier": "parent",
                                "referenced_id": "p_id",
                            },
                            {
                                "identifier": "mother",
                                "referenced_id": "m_id",
                            },
                        ],
                    },
                    0)
            )
        )

    def test_no_parent_id(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_parent_id",
        })
        self.assertEqual(
            None,
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext(
                    {
                        "indices": [
                            {
                                "identifier": "mother",
                                "referenced_id": "m_id",
                            },
                        ],
                    },
                    0)
            )
        )


class OpenInMonthExpressionTest(SimpleTestCase):
    def test_not_closed(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_open_in_month",
        })
        self.assertEqual(
            "yes",
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext(
                    {
                        "opened_on": "2015-06-03T01:10:15.241903Z",
                        "closed": False,
                    },
                    3),
            )
        )

    def test_closed_open_in_month(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_open_in_month",
        })
        self.assertEqual(
            "yes",
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext(
                    {
                        "opened_on": "2015-06-03T01:10:15.241903Z",
                        "closed": True,
                        "closed_on": "2015-08-10T01:10:15.241903Z",
                    },
                    2),
            )
        )

    def test_closed_closed_in_month(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_open_in_month",
        })
        self.assertEqual(
            "no",
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext(
                    {
                        "opened_on": "2015-06-03T01:10:15.241903Z",
                        "closed": True,
                        "closed_on": "2015-08-10T01:10:15.241903Z",
                    },
                    3),
            )
        )


class TestGetCaseFormsExpressionTest(TestCase):

    def setUp(self):
        super(TestGetCaseFormsExpressionTest, self).setUp()
        self.domain = uuid.uuid4().hex
        factory = CaseFactory(domain=self.domain)
        self.test_case_id = uuid.uuid4().hex
        factory.create_or_update_case(CaseStructure(
            case_id=self.test_case_id,
            attrs={
                'case_type': 'test',
                'create': True,
                'date_opened': datetime(2015, 1, 10),
                'date_modified': datetime(2015, 3, 10),
            },
        ))
        self._submit_form(form_date=datetime(2015, 1, 10), case_id=self.test_case_id, xmlns="xmlns_a", foo="a")
        self._submit_form(form_date=datetime(2015, 1, 11), case_id=self.test_case_id, xmlns="xmlns_a", foo="a")
        self._submit_form(form_date=datetime(2015, 2, 3), case_id=self.test_case_id, xmlns="xmlns_b", foo="b")
        self._submit_form(form_date=datetime(2015, 3, 3), case_id=self.test_case_id, xmlns="xmlns_b", foo="b")
        self._submit_form(form_date=datetime(2015, 3, 4), case_id=self.test_case_id, xmlns="xmlns_b", foo="b")
        self._submit_form(form_date=datetime(2015, 3, 5), case_id=self.test_case_id, xmlns="xmlns_c", foo="b")

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        super(TestGetCaseFormsExpressionTest, self).tearDown()

    def _submit_form(self, form_date, case_id, xmlns, foo='no'):
        form = ElementTree.Element('data')
        form.attrib['xmlns'] = xmlns
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        meta.append(_create_element_with_value('timeEnd', form_date.isoformat()))
        form.append(meta)

        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        form.append(case)

        form.append(_create_element_with_value('foo', foo))

        submit_form_locally(ElementTree.tostring(form), self.domain, **{})

    def test_all_forms(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_forms_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                }
            }
        })
        self.assertEqual(7, expression({"some_field", "some_value"}, context))

    def test_start_end(self):
        context = EvaluationContext(
            {"domain": self.domain, "start_date": "2015-03-01", "end_date": "2015-03-31"},
            0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_forms_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "start_date": {
                    "type": "ext_root_property_name",
                    "property_name": "start_date",
                    "datatype": "date",
                },
                "end_date": {
                    "type": "ext_root_property_name",
                    "property_name": "end_date",
                    "datatype": "date",
                }
            }
        })
        self.assertEqual(3, expression({"some_field": "some_val"}, context))

    def test_xmlns_single(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_forms_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "xmlns": ["xmlns_a"]
            }
        })
        self.assertEqual(2, expression({"some_field", "some_value"}, context))

    def test_xmlns_multiple(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_forms_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "xmlns": ["xmlns_a", "xmlns_b"]
            }

        })
        self.assertEqual(5, expression({"some_field", "some_value"}, context))

    def test_form_filter(self):
        context = EvaluationContext({"domain": self.domain}, 0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_forms_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "form_filter": {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_path",
                        "property_path": ["form", "foo"]
                    },
                    "property_value": "a"
                }
            }
        })
        self.assertEqual(2, expression({"some_field", "some_value"}, context))


class TestGetCaseHistoryExpressionTest(TestCase):

    def setUp(self):
        super(TestGetCaseHistoryExpressionTest, self).setUp()
        self.domain = uuid.uuid4().hex
        factory = CaseFactory(domain=self.domain)
        self.test_case_id = uuid.uuid4().hex
        factory.create_or_update_case(CaseStructure(
            case_id=self.test_case_id,
            attrs={
                'case_type': 'test',
                'create': True,
                'date_opened': datetime(2015, 1, 10),
                'date_modified': datetime(2015, 1, 10),
            },
        ))
        self._submit_form(form_date=datetime(2015, 1, 10), case_id=self.test_case_id,
                          case_path='a', xmlns="xmlns_a", foo="a")
        self._submit_form(form_date=datetime(2015, 1, 11), case_id=self.test_case_id,
                          case_path='a', xmlns="xmlns_a", foo="a")
        self._submit_form(form_date=datetime(2015, 1, 12), case_id=self.test_case_id,
                          case_path='b', xmlns="xmlns_b", foo="")
        self._submit_form(form_date=datetime(2015, 2, 3), case_id=self.test_case_id,
                          case_path='b', xmlns="xmlns_b", foo="b")
        self._submit_form(form_date=datetime(2015, 3, 4), case_id=self.test_case_id,
                          case_path='c', xmlns="xmlns_c", foo="c")

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        super(TestGetCaseHistoryExpressionTest, self).tearDown()

    def _submit_form(self, form_date, case_id, xmlns, case_path, foo='no'):
        form = ElementTree.Element('data')
        form.attrib['xmlns'] = xmlns
        form.attrib['xmlns:jrm'] = 'http://openrosa.org/jr/xforms'

        meta = ElementTree.Element('meta')
        meta.append(_create_element_with_value('timeEnd', form_date.isoformat()))
        form.append(meta)

        case_path = ElementTree.Element(case_path)
        case = ElementTree.Element('case')
        case.attrib['date_modified'] = form_date.isoformat()
        case.attrib['case_id'] = case_id
        case.attrib['xmlns'] = 'http://commcarehq.org/case/transaction/v2'
        case_update = ElementTree.Element('update')
        case_update.append(_create_element_with_value('foo', foo))
        case.append(case_update)
        case_path.append(case)
        form.append(case_path)

        form.append(_create_element_with_value('foo', foo))
        submit_form_locally(ElementTree.tostring(form), self.domain, **{})

    def test_all_history(self):
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_history",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
            }
        })
        self.assertEqual(
            6,
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"domain": self.domain}, 0),
            )
        )

    def test_filter(self):
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_history_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "filter": {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_path",
                        "property_path": ["update", "foo"]
                    },
                    "property_value": "a"
                }
            }
        })
        self.assertEqual(
            2,
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"domain": self.domain}, 0),
            )
        )

    def test_start_end(self):
        context = EvaluationContext(
            {"domain": self.domain, "start_date": "2015-03-01", "end_date": "2015-03-31"},
            0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_history_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "start_date": {
                    "type": "ext_root_property_name",
                    "property_name": "start_date",
                    "datatype": "date",
                },
                "end_date": {
                    "type": "ext_root_property_name",
                    "property_name": "end_date",
                    "datatype": "date",
                }
            }
        })
        self.assertEqual(
            1,
            expression(
                {"some_item": "item_value"},
                context=context
            )
        )

    def test_end(self):
        context = EvaluationContext(
            {"domain": self.domain, "end_date": "2015-02-28"},
            0)
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "aggregation_fn": "count",
            "items_expression": {
                "type": "ext_get_case_history_by_date",
                "case_id_expression": {
                    "type": "constant",
                    "constant": self.test_case_id
                },
                "end_date": {
                    "type": "ext_root_property_name",
                    "property_name": "end_date",
                    "datatype": "date",
                },
            }
        })
        self.assertEqual(
            5,
            expression(
                {"some_item": "item_value"},
                context=context,
            )
        )

    def test_last_update_none(self):
        expression = ExpressionFactory.from_spec({
            "type": "ext_get_last_case_property_update",
            "case_id_expression": {
                "type": "constant",
                "constant": self.test_case_id
            },
            "case_property": "bar",
        })
        self.assertEqual(
            None,
            expression(
                {"some_item": "item_value"},
                context=EvaluationContext({"domain": self.domain}, 0),
            )
        )

    def test_last_update_blank(self):
        context = EvaluationContext(
            {"domain": self.domain, "end_date": "2015-01-31"},
            0)
        expression = ExpressionFactory.from_spec({
            "type": "ext_get_last_case_property_update",
            "case_id_expression": {
                "type": "constant",
                "constant": self.test_case_id
            },
            "case_property": "foo",
            "end_date": {
                "type": "ext_root_property_name",
                "property_name": "end_date",
                "datatype": "date",
            },
        })
        self.assertEqual(
            "",
            expression(
                {"some_item": "item_value"},
                context=context,
            )
        )

    def test_last_update_value(self):
        context = EvaluationContext(
            {"domain": self.domain, "end_date": "2015-02-28"},
            0)
        expression = ExpressionFactory.from_spec({
            "type": "ext_get_last_case_property_update",
            "case_id_expression": {
                "type": "constant",
                "constant": self.test_case_id
            },
            "case_property": "foo",
            "end_date": {
                "type": "ext_root_property_name",
                "property_name": "end_date",
                "datatype": "date",
            },
        })
        self.assertEqual(
            "b",
            expression(
                {"some_item": "item_value"},
                context=context,
            )
        )

    def test_last_update_filtered(self):
        context = EvaluationContext(
            {"domain": self.domain, "end_date": "2015-01-31"},
            0)
        expression = ExpressionFactory.from_spec({
            "type": "ext_get_last_case_property_update",
            "case_id_expression": {
                "type": "constant",
                "constant": self.test_case_id
            },
            "case_property": "foo",
            "end_date": {
                "type": "ext_root_property_name",
                "property_name": "end_date",
                "datatype": "date",
            },
            "filter": {
                "type": "not",
                "filter":
                    {
                        "type": "boolean_expression",
                        "operator": "in",
                        "expression": {
                            "type": "property_path",
                            "property_path": [
                                "update",
                                "foo",
                            ]
                        },
                        "property_value": [
                            "",
                            None,
                        ]
                    }
            }
        })
        self.assertEqual(
            "a",
            expression(
                {"some_item": "item_value"},
                context=context,
            )
        )
