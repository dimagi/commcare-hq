import inspect
from uuid import uuid4

from django.db import models
from django.test import SimpleTestCase, TestCase

from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.migration import (
    SyncCouchToSQLMixin,
    SyncSQLToCouchMixin,
)

from corehq.motech.dhis2.repeaters import (
    Dhis2EntityRepeater,
    Dhis2Repeater,
    SQLDhis2EntityRepeater,
    SQLDhis2Repeater,
)
from corehq.motech.fhir.repeaters import FHIRRepeater, SQLFHIRRepeater
from corehq.motech.models import ConnectionSettings
from corehq.motech.openmrs.repeaters import OpenmrsRepeater, SQLOpenmrsRepeater
from corehq.motech.repeaters.dbaccessors import (
    delete_all_repeaters,
)
from corehq.motech.repeaters.utils import get_all_repeater_docs
from corehq.motech.repeaters.expression.repeaters import (
    CaseExpressionRepeater,
    SQLCaseExpressionRepeater,
)
from custom.cowin.repeaters import (
    BeneficiaryRegistrationRepeater,
    BeneficiaryVaccinationRepeater,
    SQLBeneficiaryRegistrationRepeater,
    SQLBeneficiaryVaccinationRepeater,
)

from ..models import (
    AppStructureRepeater,
    CaseRepeater,
    CreateCaseRepeater,
    DataRegistryCaseUpdateRepeater,
    FormRepeater,
    LocationRepeater,
    ReferCaseRepeater,
    Repeater,
    ShortFormRepeater,
    SQLAppStructureRepeater,
    SQLCaseRepeater,
    SQLCreateCaseRepeater,
    SQLDataRegistryCaseUpdateRepeater,
    SQLFormRepeater,
    SQLLocationRepeater,
    SQLReferCaseRepeater,
    SQLRepeater,
    SQLShortFormRepeater,
    SQLUpdateCaseRepeater,
    SQLUserRepeater,
    UpdateCaseRepeater,
    UserRepeater,
)


DOMAIN = 'test-domain'


class RepeaterProxyTests(TestCase):
    def setUp(self):
        self.url = "http://example.com"
        self.conn = ConnectionSettings.objects.create(domain=DOMAIN, name=self.url, url=self.url)
        self.repeater_data = {
            "domain": DOMAIN,
            "connection_settings": self.conn,
            "white_listed_case_types": ['white_case', 'black_case'],
            "black_listed_users": ['user1'],
            "is_paused": False,
            "format": 'case_json',
        }
        super().setUp()

    def tearDown(self):
        delete_all_repeaters()
        return super().tearDown()


class TestSQLRepeaterCreatesCorrectRepeaterObjects(RepeaterProxyTests):
    def setUp(self):
        super().setUp()
        self.repeater_classes = [
            SQLDhis2EntityRepeater, SQLCaseExpressionRepeater,
            SQLCaseRepeater, SQLDataRegistryCaseUpdateRepeater, SQLOpenmrsRepeater]
        for r in self.repeater_classes:
            mock_data = self.repeater_data
            r(
                domain=mock_data['domain'], connection_settings=self.conn, repeater_id=uuid4().hex
            ).save(sync_to_couch=False)

    def test_repeater_all_returns_correct_instance(self):
        all_repeaters = SQLRepeater.objects.all()
        self.assertEqual(
            {r.__class__.__name__ for r in all_repeaters},
            {r.__name__ for r in self.repeater_classes},
        )


class TestSQLCreateCaseRepeaterSubModels(RepeaterProxyTests):
    def setUp(self):
        super().setUp()
        self.createcase_repeater_obj = SQLCreateCaseRepeater(**self.repeater_data)
        self.case_repeater_obj = SQLCaseRepeater(**self.repeater_data)
        self.refercase_repeater_obj = SQLReferCaseRepeater(**self.repeater_data)
        self.dataregistry_repeater_obj = SQLDataRegistryCaseUpdateRepeater(**self.repeater_data)
        self.case_repeater_obj.save()
        self.createcase_repeater_obj.save()
        self.refercase_repeater_obj.save()
        self.dataregistry_repeater_obj.save()

    def test_model_instance_is_correct(self):
        self.assertEqual(self.createcase_repeater_obj.repeater_type, "CreateCaseRepeater")
        self.assertEqual(self.case_repeater_obj.repeater_type, "CaseRepeater")
        self.assertIsInstance(self.createcase_repeater_obj, SQLCreateCaseRepeater)
        self.assertIsInstance(self.case_repeater_obj, SQLCaseRepeater)

    def test_repeat_records_refer_correct_model_class(self):
        self.createcase_repeater_obj.repeat_records.create(
            domain=DOMAIN,
            payload_id='r2d2',
            registered_at='1977-01-01',
        )
        self.case_repeater_obj.repeat_records.create(
            domain=DOMAIN,
            payload_id='darth',
            registered_at='1980-01-01',
        )

        createcase_repeat_records = self.createcase_repeater_obj.repeat_records.all()
        case_repeat_records = self.case_repeater_obj.repeat_records.all()

        self.assertEqual(len(createcase_repeat_records), 1)
        self.assertEqual(len(case_repeat_records), 1)
        self.assertIsInstance(case_repeat_records[0].repeater, SQLCaseRepeater)
        self.assertIsInstance(createcase_repeat_records[0].repeater, SQLCreateCaseRepeater)

    def test_repeaters_are_synced_to_couch(self):
        repeaters = get_all_repeater_docs()
        self.assertEqual(len(repeaters), 4)
        self.assertEqual(
            {
                r['_id'] for r in repeaters
            },
            {
                self.createcase_repeater_obj.repeater_id,
                self.case_repeater_obj.repeater_id,
                self.refercase_repeater_obj.repeater_id,
                self.dataregistry_repeater_obj.repeater_id
            }
        )
        self.assertEqual(
            {
                Repeater.wrap(r).repeater_type for r in repeaters
            },
            {
                self.createcase_repeater_obj.repeater_type,
                self.case_repeater_obj.repeater_type,
                self.refercase_repeater_obj.repeater_type,
                self.dataregistry_repeater_obj.repeater_type
            }
        )

    def test_query_results_are_correct(self):
        self.assertEqual(len(SQLCreateCaseRepeater.objects.all()), 1)
        self.assertEqual(len(SQLCaseRepeater.objects.all()), 1)
        self.assertEqual(len(SQLReferCaseRepeater.objects.all()), 1)
        self.assertEqual(len(SQLDataRegistryCaseUpdateRepeater.objects.all()), 1)
        self.assertEqual(len(SQLRepeater.objects.all()), 4)


class TestSQLRepeaterSubClasses(RepeaterProxyTests):
    def setUp(self):
        super().setUp()
        appstructure_repeater_obj = SQLAppStructureRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
            is_paused=False,
            format='app_structure_xml',
        )
        shortform_repeater_obj = SQLShortFormRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
            is_paused=False,
            format='short_form_json',
        )
        user_repeater_obj = SQLUserRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
            is_paused=False,
            format='',
        )
        location_repeater_obj = SQLLocationRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
            is_paused=False,
            format='',
        )
        self.all_repeaters = [
            appstructure_repeater_obj, shortform_repeater_obj, user_repeater_obj, location_repeater_obj
        ]

        for r in self.all_repeaters:
            r.save()

    def test_repeaters_are_synced_to_couch(self):
        repeaters = get_all_repeater_docs()
        self.assertEqual(len(repeaters), 4)
        self.assertEqual(
            {r['_id'] for r in repeaters},
            {r.repeater_id for r in self.all_repeaters}
        )
        self.assertEqual(
            {Repeater.wrap(r).repeater_type for r in repeaters},
            {r.repeater_type for r in self.all_repeaters}
        )


class ModelAttrEqualityHelper(SimpleTestCase):
    class DummySQLModel(models.Model, SyncSQLToCouchMixin):
        pass

    class DummyCouchModel(Document, SyncCouchToSQLMixin):
        pass

    @classmethod
    def _get_user_defined_attrs(cls, model_cls, dummy_model):
        model_attrs = dir(dummy_model)
        return {item[0]
                for item in inspect.getmembers(model_cls)
                if item[0] not in model_attrs}

    @classmethod
    def get_sql_attrs(cls, model_cls):
        return cls._get_user_defined_attrs(model_cls, cls.DummySQLModel)

    @classmethod
    def get_cleaned_couch_attrs(cls, couch_model_cls):
        couch_attrs = cls._get_user_defined_attrs(couch_model_cls, cls.DummyCouchModel)
        extra_attrs = cls._couch_only_attrs()
        new_attrs = cls._sql_only_attrs()
        return (couch_attrs - extra_attrs).union(new_attrs)

    @classmethod
    def _couch_only_attrs(cls):
        return set()

    @classmethod
    def _sql_only_attrs(cls):
        return set()


class TestRepeaterModelsAttrEquality(ModelAttrEqualityHelper):

    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(Repeater)
        sql_attrs = self.get_sql_attrs(SQLRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())

    @classmethod
    def get_sql_attrs(cls, model_cls):
        sql_attrs = cls._get_user_defined_attrs(model_cls, cls.DummySQLModel)
        return sql_attrs

    @classmethod
    def _couch_only_attrs(cls):
        return {
            # removed
            'last_success_at',
            'sql_repeater',
            'failure_streak',
            'started_at',
            # renamed
            'paused',
            # connection setting props
            'plaintext_password', 'username', 'notify_addresses_str', 'create_connection_settings', 'name', 'url',
            'skip_cert_verify', 'password', 'auth_type',
            # not required in sql
            'by_domain', 'base_doc',
            'get_class_from_doc_type', 'started_at', '_get_connection_settings',
            'clear_caches',  # will see if we need it as per requirement
        }

    @classmethod
    def _sql_only_attrs(cls):
        return {
            'repeater_id', 'set_next_attempt', 'next_attempt_at',
            'is_ready', 'options', '_repeater_type', 'last_attempt_at', 'repeat_records_ready', 'repeat_records',
            'all_objects', 'reset_next_attempt', 'is_deleted', 'PROXY_FIELD_NAME', 'Meta', 'repeater',
            # added by django choicefield in models
            'get_request_method_display',
            # other attrs
            'to_json', '_convert_to_serializable',
            '_optionvalue_fields', '_wrap_schema_attrs',
        }


class TestCaseRepeaterAttrEquality(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(CaseRepeater)
        sql_attrs = self.get_sql_attrs(SQLCaseRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestFormRepeaterAttrEquality(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(FormRepeater)
        sql_attrs = self.get_sql_attrs(SQLFormRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestCreateCaseRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(CreateCaseRepeater)
        sql_attrs = self.get_sql_attrs(SQLCreateCaseRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestUpdateCaseRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(UpdateCaseRepeater)
        sql_attrs = self.get_sql_attrs(SQLUpdateCaseRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestReferCaseRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(ReferCaseRepeater)
        sql_attrs = self.get_sql_attrs(SQLReferCaseRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestDataRegistryRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(DataRegistryCaseUpdateRepeater)
        sql_attrs = self.get_sql_attrs(SQLDataRegistryCaseUpdateRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestShorFormRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(ShortFormRepeater)
        sql_attrs = self.get_sql_attrs(SQLShortFormRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestAppStructureRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(AppStructureRepeater)
        sql_attrs = self.get_sql_attrs(SQLAppStructureRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestUserRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(UserRepeater)
        sql_attrs = self.get_sql_attrs(SQLUserRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestLocationRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(LocationRepeater)
        sql_attrs = self.get_sql_attrs(SQLLocationRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestDhsi2Repeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(Dhis2Repeater)
        sql_attrs = self.get_sql_attrs(SQLDhis2Repeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestDhis2EntityRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(Dhis2EntityRepeater)
        sql_attrs = self.get_sql_attrs(SQLDhis2EntityRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestOpenMRSRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(OpenmrsRepeater)
        sql_attrs = self.get_sql_attrs(SQLOpenmrsRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestCaseExpresionRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(CaseExpressionRepeater)
        sql_attrs = self.get_sql_attrs(SQLCaseExpressionRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestFHIRRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(FHIRRepeater)
        sql_attrs = self.get_sql_attrs(SQLFHIRRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestBeneficiaryRegistrationRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(BeneficiaryRegistrationRepeater)
        sql_attrs = self.get_sql_attrs(SQLBeneficiaryRegistrationRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())


class TestBeneficiaryVaccinationRepeater(TestRepeaterModelsAttrEquality):
    def test_have_same_attrs(self):
        couch_attrs = self.get_cleaned_couch_attrs(BeneficiaryVaccinationRepeater)
        sql_attrs = self.get_sql_attrs(SQLBeneficiaryVaccinationRepeater)
        self.assertEqual(couch_attrs ^ sql_attrs, set())
