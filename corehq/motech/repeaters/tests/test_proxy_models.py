from dateutil.parser import isoparse

from django.test import TestCase

from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater
from corehq.motech.models import ConnectionSettings
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.repeaters.expression.repeaters import (
    CaseExpressionRepeater,
)

from ..models import (
    CaseRepeater,
    CreateCaseRepeater,
    DataRegistryCaseUpdateRepeater,
    ReferCaseRepeater,
    Repeater,
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


class TestRepeaterCreatesCorrectRepeaterObjects(RepeaterProxyTests):
    def setUp(self):
        super().setUp()
        self.repeater_classes = [
            Dhis2EntityRepeater, CaseExpressionRepeater,
            CaseRepeater, DataRegistryCaseUpdateRepeater, OpenmrsRepeater]
        for r in self.repeater_classes:
            mock_data = self.repeater_data
            r(
                domain=mock_data['domain'], connection_settings=self.conn
            ).save()

    def test_repeater_all_returns_correct_instance(self):
        all_repeaters = Repeater.objects.all()
        self.assertEqual(
            {r.__class__.__name__ for r in all_repeaters},
            {r.__name__ for r in self.repeater_classes},
        )


class TestCreateCaseRepeaterSubModels(RepeaterProxyTests):
    def setUp(self):
        super().setUp()
        self.createcase_repeater_obj = CreateCaseRepeater(**self.repeater_data)
        self.case_repeater_obj = CaseRepeater(**self.repeater_data)
        self.refercase_repeater_obj = ReferCaseRepeater(**self.repeater_data)
        self.dataregistry_repeater_obj = DataRegistryCaseUpdateRepeater(**self.repeater_data)
        self.case_repeater_obj.save()
        self.createcase_repeater_obj.save()
        self.refercase_repeater_obj.save()
        self.dataregistry_repeater_obj.save()

    def test_model_instance_is_correct(self):
        self.assertEqual(self.createcase_repeater_obj.repeater_type, "CreateCaseRepeater")
        self.assertEqual(self.case_repeater_obj.repeater_type, "CaseRepeater")
        self.assertIsInstance(self.createcase_repeater_obj, CreateCaseRepeater)
        self.assertIsInstance(self.case_repeater_obj, CaseRepeater)

    def test_repeat_records_refer_correct_model_class(self):
        self.createcase_repeater_obj.repeat_records.create(
            domain=DOMAIN,
            payload_id='r2d2',
            registered_at=isoparse('1977-01-01'),
            repeater_id=self.createcase_repeater_obj.id,
        )
        self.case_repeater_obj.repeat_records.create(
            domain=DOMAIN,
            payload_id='darth',
            registered_at=isoparse('1980-01-01'),
            repeater_id=self.case_repeater_obj.id,
        )

        createcase_repeat_records = self.createcase_repeater_obj.repeat_records.all()
        case_repeat_records = self.case_repeater_obj.repeat_records.all()

        self.assertEqual(len(createcase_repeat_records), 1)
        self.assertEqual(len(case_repeat_records), 1)
        self.assertIsInstance(case_repeat_records[0].repeater, CaseRepeater)
        self.assertIsInstance(createcase_repeat_records[0].repeater, CreateCaseRepeater)

    def test_query_results_are_correct(self):
        self.assertEqual(len(CreateCaseRepeater.objects.all()), 1)
        self.assertEqual(len(CaseRepeater.objects.all()), 1)
        self.assertEqual(len(ReferCaseRepeater.objects.all()), 1)
        self.assertEqual(len(DataRegistryCaseUpdateRepeater.objects.all()), 1)
        self.assertEqual(len(Repeater.objects.all()), 4)
