from django.test import TestCase

from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.dbaccessors import delete_all_repeaters, get_all_repeater_docs

from ..models import SQLCaseRepeater, SQLCreateCaseRepeater

DOMAIN = 'test-domain'


class TestSQLCreateCaseRepeater(TestCase):
    def setUp(self):
        self.url = "http://example.com"
        self.conn = ConnectionSettings.objects.create(domain=DOMAIN, name=self.url, url=self.url)
        self.createcase_repeater_obj = SQLCreateCaseRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
            white_listed_case_types=['white_case', 'black_case'],
            black_listed_users=['user1'],
            is_paused=False,
            format='case_json',
        )
        self.case_repeater_obj = SQLCaseRepeater(
            domain=DOMAIN,
            connection_settings=self.conn,
            white_listed_case_types=['white_case', 'black_case'],
            black_listed_users=['user1'],
            is_paused=False,
            format='case_json',
        )
        self.case_repeater_obj.save()
        self.createcase_repeater_obj.save()
        return super().setUp()

    def tearDown(self):
        delete_all_repeaters()
        return super().tearDown()

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
            payload_id='lilith',
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
        self.assertEqual(len(repeaters), 2)
        self.assertListEqual(
            sorted([r['_id'] for r in repeaters]),
            sorted([self.createcase_repeater_obj.repeater_id, self.case_repeater_obj.repeater_id])
        )
        self.assertListEqual(
            sorted([r['repeater_type'] for r in repeaters]),
            sorted([self.createcase_repeater_obj.repeater_type, self.case_repeater_obj.repeater_type])
        )
