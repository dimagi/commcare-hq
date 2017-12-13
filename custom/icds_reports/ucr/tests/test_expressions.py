from __future__ import absolute_import
from copy import deepcopy
import uuid
from django.test import SimpleTestCase, TestCase, override_settings
import mock
from casexml.apps.case.mock import CaseStructure, CaseFactory
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import EvaluationContext
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.toggles import ICDS_UCR_ELASTICSEARCH_DOC_LOADING, DynamicallyPredictablyRandomToggle, NAMESPACE_OTHER
from toggle.models import Toggle

es_form_cache = []


def mget_query_fake(index, ids, source):
    return [
        {"_id": form['_id'], "_source": form}
        for form in es_form_cache
        if form['_id'] in ids
    ]


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
@mock.patch('custom.icds_reports.ucr.expressions.mget_query', mget_query_fake)
class TestFormsExpressionSpecWithFilter(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestFormsExpressionSpecWithFilter, cls).setUpClass()
        global es_form_cache
        cls.domain = uuid.uuid4().hex
        factory = CaseFactory(domain=cls.domain)
        [cls.case] = factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        cls.forms = [f.to_json() for f in FormAccessors(cls.domain).get_forms(cls.case.xform_ids)]
        for form in cls.forms:
            es_form_cache.append(deepcopy(form))
        # redundant case to create extra forms that shouldn't be in the results for cls.case
        [cls.case_b] = factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        cls.forms_b = [f.to_json() for f in FormAccessors(cls.domain).get_forms(cls.case_b.xform_ids)]
        for form in cls.forms_b:
            es_form_cache.append(deepcopy(form))

    @classmethod
    def tearDownClass(cls):
        global es_form_cache
        es_form_cache = []
        delete_all_xforms()
        delete_all_cases()
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
        self.assertEqual(forms, self.forms)

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
        self.assertEqual(forms, self.forms)

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
        self.assertEqual(forms, self.forms)

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
        self.assertEqual(forms, self.forms)

        expression = self._make_expression(from_statement='iteration + 3')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 0)
        self.assertEqual(forms, [])


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
