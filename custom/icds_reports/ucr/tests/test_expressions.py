from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import uuid

from django.test import SimpleTestCase, TestCase, override_settings

from casexml.apps.case.const import CASE_INDEX_CHILD
from casexml.apps.case.mock import CaseIndex
from casexml.apps.case.mock import CaseStructure, CaseFactory
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.toggles import ICDS_UCR_ELASTICSEARCH_DOC_LOADING, DynamicallyPredictablyRandomToggle, NAMESPACE_OTHER
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping
from toggle.models import Toggle


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestFormsExpressionSpecWithFilter(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestFormsExpressionSpecWithFilter, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        factory = CaseFactory(domain=cls.domain)
        [cls.case] = factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        cls.forms = [f.to_json() for f in FormAccessors(cls.domain).get_forms(cls.case.xform_ids)]

        # redundant case to create extra forms that shouldn't be in the results for cls.case
        [cls.case_b] = factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        cls.forms_b = [f.to_json() for f in FormAccessors(cls.domain).get_forms(cls.case_b.xform_ids)]

        cls._setup_es_for_data()

    @classmethod
    def _setup_es_for_data(cls):
        cls.es = get_es_new()
        cls.es_indices = [XFORM_INDEX_INFO]
        for index_info in cls.es_indices:
            initialize_index_and_mapping(cls.es, index_info)

        for form in cls.forms + cls.forms_b:
            es_form = transform_xform_for_elasticsearch(form)
            send_to_elasticsearch('forms', es_form)

        for index_info in cls.es_indices:
            cls.es.indices.refresh(index_info.index)

    @classmethod
    def tearDownClass(cls):
        delete_all_xforms()
        delete_all_cases()
        for index_info in cls.es_indices:
            ensure_index_deleted(index_info.index)
        super(TestFormsExpressionSpecWithFilter, cls).tearDownClass()

    def _make_expression(self, from_statement=None, to_statement=None, xmlns=None, count=False):
        spec = {
            "type": "icds_get_case_forms_in_date",
            "case_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            },
        }

        if from_statement:
            spec["from_date_expression"] = {
                "type": "add_months",
                "datatype": "datetime",
                "date_expression": {
                    "type": "property_name",
                    "property_name": "server_modified_on"
                },
                "months_expression": {
                    "type": "evaluator",
                    "statement": from_statement,
                    "context_variables": {
                        "iteration": {
                            "type": "base_iteration_number"
                        }
                    }
                },
            }

        if to_statement:
            spec["to_date_expression"] = {
                "type": "add_months",
                "datatype": "datetime",
                "date_expression": {
                    "type": "property_name",
                    "property_name": "server_modified_on"
                },
                "months_expression": {
                    "type": "evaluator",
                    "statement": to_statement,
                    "context_variables": {
                        "iteration": {
                            "type": "base_iteration_number"
                        }
                    }
                },
            }

        if xmlns:
            spec['xmlns'] = [xmlns]

        spec['count'] = count

        return ExpressionFactory.from_spec(spec)

    def test_from_inside_date_range(self):
        expression = self._make_expression('iteration - 1', 'iteration + 1')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['_id'], self.forms[0]['_id'])

    def test_results_from_cache(self):
        # reuse the context to test an edge case in caching
        expression_1 = self._make_expression('iteration - 1', 'iteration + 1')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression_1(self.case.to_json(), context)
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['_id'], self.forms[0]['_id'])
        expression_2 = self._make_expression('iteration - 2', 'iteration + 1')
        forms = expression_2(self.case.to_json(), context)
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['_id'], self.forms[0]['_id'])

    def test_from_outside_date_range(self):
        expression = self._make_expression('iteration - 2', 'iteration - 1')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(forms, [])

    def test_from_correct_xmlns(self):
        expression = self._make_expression('iteration - 1', 'iteration + 1', 'http://commcarehq.org/case')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['_id'], self.forms[0]['_id'])

    def test_from_incorrect_xmlns(self):
        expression = self._make_expression('iteration - 1', 'iteration + 1', 'silly-xmlns')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(forms, [])

    def test_count_correct_xmlns(self):
        expression = self._make_expression(
            'iteration - 1', 'iteration + 1', 'http://commcarehq.org/case', count=True
        )
        context = EvaluationContext({"domain": self.domain}, 0)
        count = expression(self.case.to_json(), context)
        self.assertEqual(count, 1)

    def test_count_incorrect_xmlns(self):
        expression = self._make_expression('iteration - 1', 'iteration + 1', 'silly-xmlns', count=True)
        context = EvaluationContext({"domain": self.domain}, 0)
        count = expression(self.case.to_json(), context)
        self.assertEqual(count, 0)

    def test_no_from_statement(self):
        expression = self._make_expression(to_statement='iteration + 1')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['_id'], self.forms[0]['_id'])

        expression = self._make_expression(to_statement='iteration - 3')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 0)
        self.assertEqual(forms, [])

    def test_no_to_statement(self):
        expression = self._make_expression(from_statement='iteration - 1')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['_id'], self.forms[0]['_id'])

        expression = self._make_expression(from_statement='iteration + 3')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 0)
        self.assertEqual(forms, [])

    def test_expression_with_raw_dates(self):
        dates = [
            # hack to get just the date part
            f['server_modified_on'][0:10]
            for f in self.forms
        ]
        min_date = min(dates)
        max_date = max(dates)

        expression = ExpressionFactory.from_spec({
            "type": "icds_get_case_forms_in_date",
            "case_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            },
            "from_date_expression": {
                "type": "constant",
                "constant": min_date,
                "datatype": "date"
            },
            "to_date_expression": {
                "type": "constant",
                "constant": max_date,
                "datatype": "date"
            },
        })
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), len(self.forms))


@override_settings(DISABLE_RANDOM_TOGGLES=False)
class TestFormsExpressionSpecWithFilterEsVersion(TestFormsExpressionSpecWithFilter):
    @classmethod
    def setUpClass(cls):
        super(TestFormsExpressionSpecWithFilterEsVersion, cls).setUpClass()
        # enable toggle to 100%
        db_toggle = Toggle(slug=ICDS_UCR_ELASTICSEARCH_DOC_LOADING.slug)
        setattr(db_toggle, DynamicallyPredictablyRandomToggle.RANDOMNESS_KEY, 1)
        db_toggle.save()
        assert ICDS_UCR_ELASTICSEARCH_DOC_LOADING.enabled(uuid.uuid4().hex, NAMESPACE_OTHER)

    @classmethod
    def tearDownClass(cls):
        Toggle.get(ICDS_UCR_ELASTICSEARCH_DOC_LOADING.slug).delete()
        super(TestFormsExpressionSpecWithFilterEsVersion, cls).tearDownClass()


class TestGetAppVersion(SimpleTestCase):
    def test_cases(self):
        expression = ExpressionFactory.from_spec({
            "type": "icds_get_app_version",
            "app_version_string": {
                "type": "property_name",
                "property_name": "app_version_string",
            },
        })
        self.assertEqual(None, expression({"app_version_string": "bar"}))
        self.assertEqual(None, expression({}))
        self.assertEqual(None, expression({"app_version_string": ""}))
        self.assertEqual(9969, expression({
            "app_version_string": "CommCare Android, version 2.36.2(433756). App v9969. "
                                  "CommCare Version 2.36. Build 433756, built on: 2017-06-23"}))


class TestBooleanChoiceQuestion(SimpleTestCase):
    def _expression(self, nullable):
        return {
            "type": "icds_boolean",
            "boolean_property": {
                "type": "property_path",
                "property_path": ["child", "test"]
            },
            "true_values": ["1", "yes"],
            "false_values": ["0"],
            "nullable": nullable
        }

    def test_nullable(self):
        expression = ExpressionFactory.from_spec(self._expression(True))
        self.assertIsNone(expression({}))
        self.assertIsNone(expression({"child": {"test": "something crazy"}}))
        self.assertEqual(0, expression({"child": {"test": "0"}}))
        self.assertEqual(1, expression({"child": {"test": "1"}}))
        self.assertEqual(1, expression({"child": {"test": "yes"}}))

    def test_non_nullable(self):
        expression = ExpressionFactory.from_spec(self._expression(False))
        self.assertEqual(0, expression({}))
        self.assertEqual(0, expression({"child": {"test": "something crazy"}}))
        self.assertEqual(0, expression({"child": {"test": "0"}}))
        self.assertEqual(1, expression({"child": {"test": "1"}}))
        self.assertEqual(1, expression({"child": {"test": "yes"}}))
