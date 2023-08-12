import json
import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from django.utils.dateparse import parse_date
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from custom.abdm.const import STATUS_PENDING, STATUS_EXPIRED, STATUS_GRANTED
from custom.abdm.hiu.exceptions import HIU_ERROR_MESSAGES
from custom.abdm.hiu.models import HIUConsentRequest, HIUConsentArtefact
from custom.abdm.models import ABDMUser
from custom.abdm.tests.utils import json_from_file, convert_utc_iso_to_datetime
from custom.abdm.exceptions import (
    ERROR_FUTURE_DATE_MESSAGE,
    ERROR_CODE_REQUIRED,
    ERROR_CODE_REQUIRED_MESSAGE,
    ERROR_CODE_INVALID
)


class TestGenerateConsentsAPI(APITestCase):
    dir_path = os.path.dirname(os.path.abspath(__file__))
    generate_consent_sample_path = os.path.join(dir_path, 'data/generate_consent_request_sample.json')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user, _ = ABDMUser.objects.get_or_create(username="abdm_test", domain="abdm_test")
        cls.token = cls.user.access_token

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

    def tearDown(self):
        HIUConsentRequest.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        ABDMUser.objects.all().delete()
        super().tearDownClass()

    @classmethod
    def _sample_generate_consent_data(cls):
        consent_data = json_from_file(cls.generate_consent_sample_path)
        consent_data['permission']['dataEraseAt'] = (datetime.utcnow() + timedelta(days=1)).isoformat()
        return consent_data

    @patch('custom.abdm.hiu.views.consents.GatewayRequestHelper.post', return_value={})
    @patch('custom.abdm.hiu.views.consents.exists_by_health_id',
           return_value={'status': True})
    def test_generate_consent_request_success(self, *args):
        request_data = self._sample_generate_consent_data()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(HIUConsentRequest.objects.all().count(), 1)
        consent_request = HIUConsentRequest.objects.get(id=res.json()['id'])
        self.assertEqual(consent_request.status, STATUS_PENDING)
        self.assertEqual(consent_request.health_info_from_date,
                         convert_utc_iso_to_datetime(request_data['permission']['dateRange']['from']))
        self.assertEqual(consent_request.health_info_to_date,
                         convert_utc_iso_to_datetime(request_data['permission']['dateRange']['to']))
        self.assertEqual(consent_request.expiry_date,
                         convert_utc_iso_to_datetime(request_data['permission']['dataEraseAt']))
        self.assertEqual(consent_request.health_info_types, request_data['hiTypes'])
        self.assertEqual(consent_request.user, self.user)

    @patch('custom.abdm.hiu.views.consents.GatewayRequestHelper.post', return_value={})
    def test_generate_consent_request_validation_error(self, *args):
        request_data = self._sample_generate_consent_data()
        request_data['patient'] = {}
        request_data['permission']['dataEraseAt'] = (datetime.utcnow() - timedelta(days=1)).isoformat()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        json_res = res.json()
        self.assertEqual(json_res['error']['code'], 4400)
        self.assertEqual(len(json_res['error']['details']), 2)
        self.assertEqual(json_res['error']['details'][0],
                         {'attr': 'patient.id', 'code': ERROR_CODE_REQUIRED,
                          'detail': ERROR_CODE_REQUIRED_MESSAGE})
        self.assertEqual(json_res['error']['details'][1],
                         {'attr': 'permission.dataEraseAt', 'code': ERROR_CODE_INVALID,
                          'detail': ERROR_FUTURE_DATE_MESSAGE})
        self.assertEqual(HIUConsentRequest.objects.all().count(), 0)

    @patch('custom.abdm.hiu.views.consents.GatewayRequestHelper.post', return_value={})
    @patch('custom.abdm.hiu.views.consents.exists_by_health_id',
           return_value={'status': False})
    def test_generate_consent_request_patient_not_found(self, *args):
        request_data = self._sample_generate_consent_data()
        res = self.client.post(reverse('generate_consent_request'), data=json.dumps(request_data),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        json_res = res.json()
        self.assertEqual(json_res['error']['code'], 4407)
        self.assertEqual(json_res['error']['details'][0]['attr'], 'patient.id')
        self.assertEqual(json_res['error']['details'][0]['code'], ERROR_CODE_INVALID)
        self.assertEqual(json_res['error']['details'][0]['detail'], HIU_ERROR_MESSAGES[4407])
        self.assertEqual(HIUConsentRequest.objects.all().count(), 0)


class TestListConsentsAndArtefactsAPI(APITestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user, _ = ABDMUser.objects.get_or_create(username="abdm_test", domain="abdm_test")
        cls.token = cls.user.access_token
        cls.consent_ids = ['62d4c2e9-3393-42c4-ba2d-41eace1bfc00', '44ca4431-85ec-405f-8d5f-f49331bfb43f']
        cls._add_consents_data()

    @classmethod
    def _add_consents_data(cls):
        consent_data_1 = {
            'consent_request_id': cls.consent_ids[0],
            'status': STATUS_GRANTED,
            'health_info_from_date': '2011-05-17T15:12:43.960000Z',
            'health_info_to_date': '2017-08-07T15:12:43.961000Z',
            'health_info_types': [
                "DischargeSummary",
                "Prescription",
                "WellnessRecord"
            ],
            'expiry_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
            'details': {
                'patient': {
                    'id': 'test1@sbx'
                }
            }
        }
        consent_request_1 = HIUConsentRequest.objects.create(**consent_data_1, user=cls.user)
        artefact_data_1 = {
            'artefact_id': uuid.uuid4(),
            'details': {
                'hip': {
                    'id': '6004',
                    'name': 'Test Eye Care Center '
                },
            }
        }
        artefact_data_2 = {
            'artefact_id': uuid.uuid4(),
            'details': {
                'hip': {
                    'id': '6005',
                    'name': 'Demo Clinic'
                },
            }
        }
        HIUConsentArtefact.objects.create(**artefact_data_1, consent_request=consent_request_1)
        HIUConsentArtefact.objects.create(**artefact_data_2, consent_request=consent_request_1)
        consent_data_2 = {
            'consent_request_id': cls.consent_ids[1],
            'status': STATUS_EXPIRED,
            'health_info_from_date': '2021-05-17T15:12:43.960000Z',
            'health_info_to_date': '2023-08-07T15:12:43.961000Z',
            'health_info_types': [
                "WellnessRecord"
            ],
            'expiry_date': (datetime.utcnow() + timedelta(days=2)).isoformat(),
            'details': {
                'patient': {
                    'id': 'test2@sbx'
                }
            }
        }
        HIUConsentRequest.objects.create(**consent_data_2, user=cls.user)

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token)

    @classmethod
    def tearDownClass(cls):
        HIUConsentArtefact.objects.all().delete()
        HIUConsentRequest.objects.all().delete()
        ABDMUser.objects.all().delete()
        super().tearDownClass()

    def test_list_consents(self):
        res = self.client.get(reverse('consents_list'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 2)

    def test_list_consents_filter_status(self):
        params = {"status": STATUS_EXPIRED}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["results"][0]["status"], params["status"])

    def test_list_consents_filter_abha_id(self):
        params = {"abha_id": "test1@sbx"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["results"][0]["details"]["patient"]["id"], params["abha_id"])

    def test_list_consents_filter_search(self):
        params = {"search": "prescript"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertTrue(any(params["search"].casefold() in hi_type.casefold()
                            for hi_type in res.json()["results"][0]["health_info_types"]))

    def test_list_consents_filter_from_date(self):
        params = {"from_date": "2018-07-10"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertGreaterEqual(convert_utc_iso_to_datetime(
            res.json()["results"][0]["health_info_to_date"]).date(),
            parse_date(params["from_date"])
        )

    def test_list_consents_filter_to_date(self):
        params = {"to_date": "2016-05-18"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertLessEqual(convert_utc_iso_to_datetime(res.json()["results"][0]["health_info_from_date"]).date(),
                             parse_date(params["to_date"]))

    def test_list_consents_filter_from_and_to_date(self):
        params = {"from_date": "2015-07-10", "to_date": "2022-05-18"}
        res = self.client.get(reverse('consents_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 2)
        for result in res.json()["results"]:
            self.assertGreaterEqual(convert_utc_iso_to_datetime(result["health_info_to_date"]).date(),
                                    parse_date(params["from_date"]))
            self.assertLessEqual(convert_utc_iso_to_datetime(result["health_info_from_date"]).date(),
                                 parse_date(params["to_date"]))

    def test_list_consent_artefacts_no_consent_id(self):
        res = self.client.get(reverse('artefacts_list'))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error']['details'][0],
                         {'attr': 'consent_request_id', 'code': ERROR_CODE_REQUIRED,
                          'detail': ERROR_CODE_REQUIRED_MESSAGE})

    def test_list_consent_artefacts_consent_id(self):
        params = {"consent_request_id": self.consent_ids[0]}
        res = self.client.get(reverse('artefacts_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 2)
        for result in res.json()["results"]:
            self.assertEqual(result["consent_request"], params['consent_request_id'])

    def test_list_consents_artefacts_search(self):
        params = {"consent_request_id": self.consent_ids[0], "search": "test eye"}
        res = self.client.get(reverse('artefacts_list'), data=params)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertIn(params["search"].casefold(), res.json()["results"][0]["details"]["hip"]["name"].casefold())
