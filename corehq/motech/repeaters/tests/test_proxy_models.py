from django.test import TestCase

from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import (
    delete_all_repeaters,
    get_all_repeater_docs,
)

from ..models import (
    Repeater,
    SQLAppStructureRepeater,
    SQLCaseRepeater,
    SQLCreateCaseRepeater,
    SQLDataRegistryCaseUpdateRepeater,
    SQLLocationRepeater,
    SQLReferCaseRepeater,
    SQLRepeater,
    SQLShortFormRepeater,
    SQLUserRepeater,
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
