from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import uuid

from django.test import SimpleTestCase, TestCase, override_settings

from casexml.apps.case.const import CASE_INDEX_CHILD, CASE_INDEX_EXTENSION
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
from corehq.util.test_utils import generate_cases
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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class _TestOwnerIDBase(TestCase):
    awc_owner_id = uuid.uuid4().hex
    domain_name = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super(_TestOwnerIDBase, cls).setUpClass()
        cls.case_factory = CaseFactory(domain=cls.domain_name)
        cls._create_cases()

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        super(_TestOwnerIDBase, cls).tearDownClass()


class TestLegacyCaseStructureOwnerID(_TestOwnerIDBase):
    @classmethod
    def _create_cases(cls):
        household_case = CaseStructure(
            attrs={
                'case_type': 'household',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
        )

        father_person_case = CaseStructure(
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type='household',
            )],
        )

        mother_person_case = CaseStructure(
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type='household',
            )],
        )

        ccs_record_case = CaseStructure(
            attrs={
                'case_type': 'ccs_record',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
            indices=[CaseIndex(
                mother_person_case,
                identifier='parent',
                relationship=CASE_INDEX_CHILD,
                related_type=mother_person_case.attrs['case_type'],
            )],
        )

        child_health_person_case = CaseStructure(
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
            indices=[
                CaseIndex(
                    household_case,
                    identifier='parent',
                    relationship=CASE_INDEX_CHILD,
                    related_type='household',
                ),
                CaseIndex(
                    mother_person_case,
                    identifier='mother',
                    relationship=CASE_INDEX_CHILD,
                    related_type=mother_person_case.attrs['case_type'],
                )
            ],
        )

        child_health_case = CaseStructure(
            attrs={
                'case_type': 'child_health',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
            indices=[
                CaseIndex(
                    child_health_person_case,
                    identifier='parent',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type=child_health_person_case.attrs['case_type'],
                )
            ],
        )
        cls.household_case = cls.case_factory.create_or_update_case(household_case)[0]
        cls.father_person_case = cls.case_factory.create_or_update_case(father_person_case)[0]
        cls.mother_person_case = cls.case_factory.create_or_update_case(mother_person_case)[0]
        cls.ccs_record_case = cls.case_factory.create_or_update_case(ccs_record_case)[0]
        cls.child_health_person_case = cls.case_factory.create_or_update_case(child_health_person_case)[0]
        cls.child_health_case = cls.case_factory.create_or_update_case(child_health_case)[0]


@generate_cases([
    ('household_case',),
    ('father_person_case',),
    ('mother_person_case',),
    ('ccs_record_case',),
    ('child_health_person_case',),
    ('child_health_case',),
], TestLegacyCaseStructureOwnerID)
def test_awc_owner_id(self, case):
    expression = ExpressionFactory.from_spec({
        "type": "icds_awc_owner_id",
        "case_id_expression": {
            "type": "property_name",
            "property_name": "case_id",
        },
    })
    self.assertEqual(self.awc_owner_id, expression(getattr(self, case).to_json()))


@generate_cases([
    ('household_case',),
    # ('awc_ownership_case',), currently returns AWC. Should it return village?
    ('father_person_case',),
    ('mother_person_case',),
    ('ccs_record_case',),
    ('child_health_person_case',),
    ('child_health_case',),
], TestLegacyCaseStructureOwnerID)
def test_reach_village_owner_id(self, case):
    expression = ExpressionFactory.from_spec({
        "type": "icds_village_owner_id",
        "case_id_expression": {
            "type": "property_name",
            "property_name": "case_id",
        },
    })
    context = EvaluationContext({"domain": self.domain_name}, 0)
    self.assertEqual(None, expression(getattr(self, case).to_json(), context))


class TestREACHCaseStructureOwnerID(_TestOwnerIDBase):
    awc_owner_id = uuid.uuid4().hex
    village_owner_id = uuid.uuid4().hex

    @classmethod
    def _create_cases(cls):
        household_case = CaseStructure(
            attrs={
                'case_type': 'household',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': '-',
                'update': dict()
            },
        )

        awc_ownership_case = CaseStructure(
            attrs={
                'case_type': 'assignment',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.awc_owner_id,
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='awc',
                relationship=CASE_INDEX_EXTENSION,
                related_type='household',
            )],
        )

        village_ownership_case = CaseStructure(
            attrs={
                'case_type': 'assignment',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': cls.village_owner_id,
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='village',
                relationship=CASE_INDEX_EXTENSION,
                related_type='household',
            )],
        )

        father_person_case = CaseStructure(
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': '-',
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_EXTENSION,
                related_type='household',
            )],
        )

        mother_person_case = CaseStructure(
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': '-',
                'update': dict()
            },
            indices=[CaseIndex(
                household_case,
                identifier='parent',
                relationship=CASE_INDEX_EXTENSION,
                related_type='household',
            )],
        )

        ccs_record_case = CaseStructure(
            attrs={
                'case_type': 'ccs_record',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': '-',
                'update': dict()
            },
            indices=[CaseIndex(
                mother_person_case,
                identifier='parent',
                relationship=CASE_INDEX_EXTENSION,
                related_type=mother_person_case.attrs['case_type'],
            )],
        )

        child_health_person_case = CaseStructure(
            attrs={
                'case_type': 'person',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': '-',
                'update': dict()
            },
            indices=[
                CaseIndex(
                    household_case,
                    identifier='parent',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type='household',
                ),
                CaseIndex(
                    mother_person_case,
                    identifier='mother',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type='person',
                )
            ],
        )

        child_health_case = CaseStructure(
            attrs={
                'case_type': 'child_health',
                'create': True,
                'date_opened': datetime.utcnow(),
                'date_modified': datetime.utcnow(),
                'owner_id': '-',
                'update': dict()
            },
            indices=[
                CaseIndex(
                    child_health_person_case,
                    identifier='parent',
                    relationship=CASE_INDEX_EXTENSION,
                    related_type=child_health_person_case.attrs['case_type'],
                )
            ],
        )
        cls.household_case = cls.case_factory.create_or_update_case(household_case)[0]
        cls.awc_ownership_case = cls.case_factory.create_or_update_case(awc_ownership_case)[0]
        cls.village_ownership_case = cls.case_factory.create_or_update_case(village_ownership_case)[0]
        cls.father_person_case = cls.case_factory.create_or_update_case(father_person_case)[0]
        cls.mother_person_case = cls.case_factory.create_or_update_case(mother_person_case)[0]
        cls.ccs_record_case = cls.case_factory.create_or_update_case(ccs_record_case)[0]
        cls.child_health_person_case = cls.case_factory.create_or_update_case(child_health_person_case)[0]
        cls.child_health_case = cls.case_factory.create_or_update_case(child_health_case)[0]


@generate_cases([
    ('household_case',),
    ('awc_ownership_case',),
    # ('village_ownership_case',), currently returns village. Should it return AWC?
    ('father_person_case',),
    ('mother_person_case',),
    ('ccs_record_case',),
    ('child_health_person_case',),
    ('child_health_case',),
], TestREACHCaseStructureOwnerID)
def test_reach_awc_owner_id(self, case):
    expression = ExpressionFactory.from_spec({
        "type": "icds_awc_owner_id",
        "case_id_expression": {
            "type": "property_name",
            "property_name": "case_id",
        },
    })
    context = EvaluationContext({"domain": self.domain_name}, 0)
    self.assertEqual(self.awc_owner_id, expression(getattr(self, case).to_json(), context))


@generate_cases([
    ('household_case',),
    # ('awc_ownership_case',), currently returns AWC. Should it return village?
    ('village_ownership_case',),
    ('father_person_case',),
    ('mother_person_case',),
    ('ccs_record_case',),
    ('child_health_person_case',),
    ('child_health_case',),
], TestREACHCaseStructureOwnerID)
def test_reach_village_owner_id(self, case):
    expression = ExpressionFactory.from_spec({
        "type": "icds_village_owner_id",
        "case_id_expression": {
            "type": "property_name",
            "property_name": "case_id",
        },
    })
    context = EvaluationContext({"domain": self.domain_name}, 0)
    self.assertEqual(self.village_owner_id, expression(getattr(self, case).to_json(), context))
