from uuid import uuid4

from django.test import TestCase

from corehq.motech.dhis2.repeaters import SQLDhis2EntityRepeater
from corehq.motech.models import ConnectionSettings
from corehq.motech.openmrs.repeaters import SQLOpenmrsRepeater
from corehq.motech.repeaters.dbaccessors import delete_all_repeaters
from corehq.motech.repeaters.expression.repeaters import (
    SQLCaseExpressionRepeater,
)

from ..models import (
    SQLCaseRepeater,
    SQLCreateCaseRepeater,
    SQLDataRegistryCaseUpdateRepeater,
    SQLReferCaseRepeater,
    SQLRepeater,
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
            ).save()

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
            repeater_id=uuid4().hex,
        )
        self.case_repeater_obj.repeat_records.create(
            domain=DOMAIN,
            payload_id='darth',
            registered_at='1980-01-01',
            repeater_id=uuid4().hex,
        )

        createcase_repeat_records = self.createcase_repeater_obj.repeat_records.all()
        case_repeat_records = self.case_repeater_obj.repeat_records.all()

        self.assertEqual(len(createcase_repeat_records), 1)
        self.assertEqual(len(case_repeat_records), 1)
        self.assertIsInstance(case_repeat_records[0].repeater, SQLCaseRepeater)
        self.assertIsInstance(createcase_repeat_records[0].repeater, SQLCreateCaseRepeater)

    def test_query_results_are_correct(self):
        self.assertEqual(len(SQLCreateCaseRepeater.objects.all()), 1)
        self.assertEqual(len(SQLCaseRepeater.objects.all()), 1)
        self.assertEqual(len(SQLReferCaseRepeater.objects.all()), 1)
        self.assertEqual(len(SQLDataRegistryCaseUpdateRepeater.objects.all()), 1)
        self.assertEqual(len(SQLRepeater.objects.all()), 4)
