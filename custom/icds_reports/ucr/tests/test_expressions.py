from __future__ import absolute_import
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
from custom.icds_reports.ucr.expressions import icds_get_related_docs_ids
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestICDSRelatedDocs(TestCase):
    @classmethod
    def _create_cases(cls, ccs_case_id, child_health_case_id):
        household_case = CaseStructure(
            case_id='hh-' + ccs_case_id,
            attrs={
                'case_type': 'household',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
        )

        irrelavant_person_case = CaseStructure(
            case_id='person-other-' + ccs_case_id,
            attrs={
                'case_type': 'other-person-level',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=household_case.attrs['case_type'],
            )],
        )

        ccs_record_person_case = CaseStructure(
            case_id='p-' + ccs_case_id,
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=household_case.attrs['case_type'],
            )],
        )

        irrelavant_ccs_case = CaseStructure(
            case_id='ccs-other-' + ccs_case_id,
            attrs={
                'case_type': 'other',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
            indices=[CaseIndex(
                ccs_record_person_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=ccs_record_person_case.attrs['case_type'],
            )],
        )

        ccs_record_case = CaseStructure(
            case_id=ccs_case_id,
            attrs={
                'case_type': 'ccs_record',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
            indices=[CaseIndex(
                ccs_record_person_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=ccs_record_person_case.attrs['case_type'],
            )],
        )

        child_health_person_case = CaseStructure(
            case_id='p-' + child_health_case_id,
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=household_case.attrs['case_type'],
            )],
        )

        child_health_case = CaseStructure(
            case_id=child_health_case_id,
            attrs={
                'case_type': 'child_health',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'update': dict()
            },
            indices=[CaseIndex(
                child_health_person_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=ccs_record_person_case.attrs['case_type'],
            )],
        )
        cls.casefactory.create_or_update_cases(
            [ccs_record_case, child_health_case, irrelavant_person_case, irrelavant_ccs_case]
        )

    @classmethod
    def setUpClass(cls):
        super(TestICDSRelatedDocs, cls).setUpClass()
        cls.casefactory = CaseFactory(domain='icds-cas')
        cls.ccs_record_id = uuid.uuid4().hex
        cls.child_health_case_id = uuid.uuid4().hex
        cls._create_cases(cls.ccs_record_id, cls.child_health_case_id)

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        super(TestICDSRelatedDocs, cls).tearDownClass()

    def test_ccs_record_case(self):
        self.assertEqual(icds_get_related_docs_ids(self.ccs_record_id), [self.child_health_case_id])

    def test_child_health_case(self):
        self.assertEqual(icds_get_related_docs_ids(self.child_health_case_id), [self.ccs_record_id])

    def test_irrelavant_person_level_case(self):
        self.assertEqual(icds_get_related_docs_ids('person-other-' + self.ccs_record_id), [])

    def test_irrelavant_ccs_level_case(self):
        self.assertEqual(icds_get_related_docs_ids('ccs-other-' + self.ccs_record_id), [])

    def test_nonexistant_case(self):
        self.assertEqual(icds_get_related_docs_ids('nothing'), [])

    def test_household_case(self):
        self.assertEqual(icds_get_related_docs_ids('hh-' + self.ccs_record_id), [])

    def test_person_case(self):
        self.assertEqual(icds_get_related_docs_ids('p-' + self.ccs_record_id), [])
        self.assertEqual(icds_get_related_docs_ids('p-' + self.child_health_case_id), [])
