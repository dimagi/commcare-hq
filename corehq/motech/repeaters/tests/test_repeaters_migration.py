from copy import deepcopy
from django.core.management import call_command
from django.test import TestCase

from corehq.motech.dhis2.repeaters import (
    Dhis2EntityRepeater,
    Dhis2Repeater,
    SQLDhis2EntityRepeater,
    SQLDhis2Repeater,
)
from corehq.motech.fhir.repeaters import SQLFHIRRepeater
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import delete_all_repeaters
from corehq.motech.repeaters.expression.repeaters import (
    CaseExpressionRepeater,
    SQLCaseExpressionRepeater,
)
from corehq.motech.repeaters.models import (
    AppStructureRepeater,
    CaseRepeater,
    CreateCaseRepeater,
    DataRegistryCaseUpdateRepeater,
    FormRepeater,
    LocationRepeater,
    ReferCaseRepeater,
    Repeater,
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
    ShortFormRepeater,
    UpdateCaseRepeater,
    UserRepeater,
)
from corehq.motech.openmrs.repeaters import OpenmrsRepeater, SQLOpenmrsRepeater

from .data.repeaters import repeater_test_data

DOMAIN = 'r-test'


class TestMigrationCommand(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.conn = ConnectionSettings(url="http://url.com", domain='rtest')
        cls.conn.save()
        cls.couch_repeaters = []
        for r in deepcopy(repeater_test_data):
            r = Repeater.wrap(r)
            r.connection_settings_id = cls.conn.id
            r.save(sync_to_sql=False)
            cls.couch_repeaters.append(r)
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        delete_all_repeaters()
        return super().tearDownClass()

    def test_repeater_docs_are_migrated(self):
        call_command('migrate_caserepeater')
        self._assert_repeaters_equality(SQLCaseRepeater, "CaseRepeater")
        call_command('migrate_formrepeater')
        self._assert_repeaters_equality(SQLFormRepeater, "FormRepeater")
        call_command('migrate_shortformrepeater')
        self._assert_repeaters_equality(SQLShortFormRepeater, "ShortFormRepeater")
        call_command('migrate_createcaserepeater')
        self._assert_repeaters_equality(SQLCreateCaseRepeater, "CreateCaseRepeater")
        call_command('migrate_refercaserrepeater')
        self._assert_repeaters_equality(SQLReferCaseRepeater, "ReferCaseRepeater")
        call_command('migrate_dhis2repeater')
        self._assert_repeaters_equality(SQLDhis2Repeater, "Dhis2Repeater")
        call_command('migrate_userrepeater')
        self._assert_repeaters_equality(SQLUserRepeater, "UserRepeater")
        call_command('migrate_fhirrepeater')
        self._assert_repeaters_equality(SQLFHIRRepeater, "FHIRRepeater")
        call_command('migrate_appstructurerepeater')
        self._assert_repeaters_equality(SQLAppStructureRepeater, "AppStructureRepeater")
        call_command('migrate_caseexpressionrepeater')
        self._assert_repeaters_equality(SQLCaseExpressionRepeater, "CaseExpressionRepeater")
        call_command('migrate_dataregistrycaseupdaterepeater')
        self._assert_repeaters_equality(SQLDataRegistryCaseUpdateRepeater, "DataRegistryCaseUpdateRepeater")
        call_command('migrate_dhis2entityrepeater')
        self._assert_repeaters_equality(SQLDhis2EntityRepeater, "Dhis2EntityRepeater")
        call_command('migrate_openmrsrepeater')
        self._assert_repeaters_equality(SQLOpenmrsRepeater, "OpenmrsRepeater")
        call_command('migrate_locationrepeater')
        self._assert_repeaters_equality(SQLLocationRepeater, "LocationRepeater")
        call_command('migrate_updatecaserepeater')
        self._assert_repeaters_equality(SQLUpdateCaseRepeater, "UpdateCaseRepeater")

        # test for count
        self.assertEqual(SQLRepeater.objects.count(), len(self.couch_repeaters))

    def _assert_repeaters_equality(self, sql_class, doc_type):
        sql_ids = set(sql_class.objects.all().values_list('repeater_id', flat=True))
        couch_ids = {r._id for r in self._get_repeater_objects(doc_type)}
        self.assertEqual(len(couch_ids), 2)
        self.assertEqual(len(sql_ids), 2)
        self.assertCountEqual(sql_ids, couch_ids)
        self.assertEqual(sql_ids, couch_ids)

    def test_equality_of_config_attrs(self):
        call_command('migrate_dhis2repeater')
        call_command('migrate_openmrsrepeater')
        call_command('migrate_caseexpressionrepeater')
        dhsi2_objects = self._get_repeater_objects('Dhis2Repeater')
        openmrs_objects = self._get_repeater_objects('OpenmrsRepeater')
        caseexpression_objects = self._get_repeater_objects('CaseExpressionRepeater')

        for obj in dhsi2_objects:
            sql_obj = SQLDhis2Repeater.objects.get(repeater_id=obj._id)
            self.assertEqual(sql_obj.dhis2_config, obj.dhis2_config.to_json())

        for obj in openmrs_objects:
            sql_obj = SQLOpenmrsRepeater.objects.get(repeater_id=obj._id)
            self.assertEqual(sql_obj.openmrs_config, obj.openmrs_config.to_json())
            self.assertEqual(sql_obj.atom_feed_status, obj.atom_feed_status)

        for obj in caseexpression_objects:
            sql_obj = SQLCaseExpressionRepeater.objects.get(repeater_id=obj._id)
            self.assertEqual(sql_obj.configured_filter, obj.configured_filter)
            self.assertEqual(sql_obj.configured_expression, obj.configured_expression)

    def test_migrate_all_repeaters_command(self):
        call_command('migrate_all_repeaters')
        self.assertEqual(SQLRepeater.objects.count(), len(self.couch_repeaters))
        sql_ids = set(SQLRepeater.objects.all().values_list('repeater_id', flat=True))
        couch_ids = {r._id for r in self.couch_repeaters}
        self.assertEqual(sql_ids, couch_ids)

    def _get_repeater_objects(self, repeater_type):
        return [r for r in self.couch_repeaters if r.doc_type == repeater_type]


class RepeaterSyncTestsBase(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.url = "http://example.com"
        cls.conn = ConnectionSettings.objects.create(domain=DOMAIN, name=cls.url, url=cls.url)

        cls.test_data = deepcopy(repeater_test_data)
        for r in cls.test_data:
            r['connection_settings_id'] = cls.conn.id
        return super().setUpClass()

    def setUp(self):
        return super().setUp()

    def tearDown(self):
        delete_all_repeaters()
        return super().tearDown()

    def _assert_common_attrs_are_equal(self, sql_repeater, couch_repeater):
        self.assertEqual(sql_repeater.domain, couch_repeater.domain)
        self.assertEqual(sql_repeater.repeater_id, couch_repeater._id)
        self.assertEqual(sql_repeater.format, couch_repeater.format)
        self.assertEqual(sql_repeater.is_paused, couch_repeater.paused)
        self.assertEqual(sql_repeater.connection_settings.id, couch_repeater.connection_settings_id)

    def get_couch_objects(self, couch_cls):
        return [couch_cls.wrap(r) for r in self.test_data if r['doc_type'] == couch_cls.__name__]

    def get_sql_objects(self, sql_cls):
        return [sql_cls(**r) for r in self.test_data if r['doc_type'] == sql_cls._repeater_type]


class TestSQLCaseRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.white_listed_case_types, couch_repeater.white_listed_case_types)
        self.assertEqual(sql_repeater.black_listed_users, couch_repeater.black_listed_users)

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(CaseRepeater):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = SQLCaseRepeater.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(SQLCaseRepeater):
            sql_repeater.save()
            couch_repeater_dict = CaseRepeater.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = CaseRepeater.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_save_with_no_connection_settings(self):
        repeater = CaseRepeater(
            domain='test-domain',
            url='https://example.com/create-case/',
            format='case_json',
            white_listed_case_types=['test_case_type'],
        )
        self.addCleanup(repeater.delete)
        repeater.save()

        num_case_repeaters = SQLCaseRepeater.objects.filter(repeater_id=repeater._id).count()
        self.assertEqual(num_case_repeaters, 1)
        num_repeaters = SQLRepeater.objects.filter(repeater_id=repeater._id).count()
        self.assertEqual(num_repeaters, 1)


class TestSQLFormRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.include_app_id_param, couch_repeater.include_app_id_param)
        self.assertEqual(sql_repeater.white_listed_form_xmlns, couch_repeater.white_listed_form_xmlns)

    @property
    def couch_cls(cls):
        return FormRepeater

    @property
    def sql_cls(cls):
        return SQLFormRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLCreateCaseRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return CreateCaseRepeater

    @property
    def sql_cls(cls):
        return SQLCreateCaseRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLUpdateCaseRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return UpdateCaseRepeater

    @property
    def sql_cls(cls):
        return SQLUpdateCaseRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLReferCaseRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return ReferCaseRepeater

    @property
    def sql_cls(cls):
        return SQLReferCaseRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLDataRegistryRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return DataRegistryCaseUpdateRepeater

    @property
    def sql_cls(cls):
        return SQLDataRegistryCaseUpdateRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLShortFormRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.version, couch_repeater.version)

    @property
    def couch_cls(cls):
        return ShortFormRepeater

    @property
    def sql_cls(cls):
        return SQLShortFormRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLAppStructureRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return AppStructureRepeater

    @property
    def sql_cls(cls):
        return SQLAppStructureRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestUserRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return UserRepeater

    @property
    def sql_cls(cls):
        return SQLUserRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLLocationRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return LocationRepeater

    @property
    def sql_cls(cls):
        return SQLLocationRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLDhis2Repeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.dhis2_config, couch_repeater.dhis2_config.to_json())
        self.assertEqual(sql_repeater.dhis2_version, couch_repeater.dhis2_version)
        self.assertEqual(
            sql_repeater.dhis2_version_last_modified,
            couch_repeater.dhis2_version_last_modified
        )
        self.assertEqual(sql_repeater.include_app_id_param, couch_repeater.include_app_id_param)
        self.assertEqual(sql_repeater.white_listed_form_xmlns, couch_repeater.white_listed_form_xmlns)

    @property
    def couch_cls(cls):
        return Dhis2Repeater

    @property
    def sql_cls(cls):
        return SQLDhis2Repeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLDhis2EntityRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.dhis2_entity_config, couch_repeater.dhis2_entity_config.to_json())
        self.assertEqual(sql_repeater.dhis2_version, couch_repeater.dhis2_version)
        self.assertEqual(sql_repeater.dhis2_version_last_modified, couch_repeater.dhis2_version_last_modified)
        self.assertEqual(sql_repeater.white_listed_case_types, couch_repeater.white_listed_case_types)
        self.assertEqual(sql_repeater.black_listed_users, couch_repeater.black_listed_users)

    @property
    def couch_cls(cls):
        return Dhis2EntityRepeater

    @property
    def sql_cls(cls):
        return SQLDhis2EntityRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLOpenmrsRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.location_id, couch_repeater.location_id)
        self.assertEqual(sql_repeater.atom_feed_enabled, couch_repeater.atom_feed_enabled)
        self.assertEqual(sql_repeater.atom_feed_status, couch_repeater.atom_feed_status)
        # self.assertEqual(sql_repeater.openmrs_config, couch_repeater.openmrs_config.to_json())
        self.assertEqual(sql_repeater.white_listed_case_types, couch_repeater.white_listed_case_types)
        self.assertEqual(sql_repeater.black_listed_users, couch_repeater.black_listed_users)

    @property
    def couch_cls(cls):
        return OpenmrsRepeater

    @property
    def sql_cls(cls):
        return SQLOpenmrsRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLCaseExpressionRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)
        self.assertEqual(sql_repeater.configured_filter, couch_repeater.configured_filter)
        self.assertEqual(sql_repeater.configured_expression, couch_repeater.configured_expression)

    @property
    def couch_cls(cls):
        return CaseExpressionRepeater

    @property
    def sql_cls(cls):
        return SQLCaseExpressionRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)


class TestSQLUserRepeater(RepeaterSyncTestsBase):

    def _assert_same_repeater_objects(self, sql_repeater, couch_repeater):
        self._assert_common_attrs_are_equal(sql_repeater, couch_repeater)

    @property
    def couch_cls(cls):
        return UserRepeater

    @property
    def sql_cls(cls):
        return SQLUserRepeater

    def test_repeaters_are_synced_to_sql(self):
        for couch_repeater in self.get_couch_objects(self.couch_cls):
            couch_repeater.save()
            self.addCleanup(couch_repeater.delete)
            sql_repeater = self.sql_cls.objects.get(repeater_id=couch_repeater._id)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)

    def test_repeaters_are_synced_to_couch(self):
        for sql_repeater in self.get_sql_objects(self.sql_cls):
            sql_repeater.save()
            couch_repeater_dict = self.couch_cls.get_db().get(sql_repeater.repeater_id)
            self.assertIsNotNone(couch_repeater_dict)
            couch_repeater = self.couch_cls.wrap(couch_repeater_dict)
            self.addCleanup(couch_repeater.delete)
            self._assert_same_repeater_objects(sql_repeater, couch_repeater)
