from django.core.management import call_command
from django.test import TestCase

from corehq.motech.dhis2.repeaters import (
    SQLDhis2EntityRepeater,
    SQLDhis2Repeater,
)
from corehq.motech.fhir.repeaters import SQLFHIRRepeater
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import delete_all_repeaters
from corehq.motech.repeaters.expression.repeaters import (
    SQLCaseExpressionRepeater,
)
from corehq.motech.repeaters.models import (
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
)
from corehq.motech.openmrs.repeaters import SQLOpenmrsRepeater

from .data.repeaters import repeater_test_data


class TestMigrationCommand(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.conn = ConnectionSettings(id=1, url="http://url.com", domain='rtest')
        cls.conn.save()
        cls.couch_repeaters = []
        for r in repeater_test_data:
            r = Repeater.wrap(r)
            r.save(sync_to_sql=False)
            cls.couch_repeaters.append(r)
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        delete_all_repeaters()
        return super().tearDownClass()

    def test_case_repeater_docs_are_migrated(self):
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

    def _get_repeater_objects(self, repeater_type):
        return [r for r in self.couch_repeaters if r.doc_type == repeater_type]
