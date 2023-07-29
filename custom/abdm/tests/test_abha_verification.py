from unittest.mock import patch, Mock
from django.test import override_settings

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from custom.abdm.models import ABDMUser


class TestABHAVerification(APITestCase):

    def setUp(self):
        self.user, _ = ABDMUser.objects.get_or_create(username="abdm_test", domain="abdm_test")
        token = self.user.access_token
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.invalid_req_msg = "Unable to process the current request due to incorrect data entered."

    @staticmethod
    def _mock_abdm_http_post(url, payload):
        abdm_txn_id_mock = {"txnId": "1234"}
        return {
            "v1/search/searchByHealthId": {"authMethods": ["MOBILE_OTP"]},
            "v1/auth/init": abdm_txn_id_mock,
            "v1/auth/confirmWithMobileOTP": abdm_txn_id_mock,
            "v1/auth/confirmWithAadhaarOtp": abdm_txn_id_mock,
            "v1/search/existsByHealthId": {"status": True}
        }.get(url)

    @staticmethod
    def _get_health_card_mock_response(**kwargs):
        health_card_response_mock = Mock()
        health_card_response_mock.status_code = 200
        health_card_response_mock.content = b'image'
        return health_card_response_mock

    def test_getting_auth_methods_success(self):
        with patch('custom.abdm.milestone_one.views.abha_verification_views.abdm_util.get_response_http_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.get(reverse("get_auth_methods"), {"health_id": "123456"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'auth_methods': ['MOBILE_OTP']})

    def test_getting_auth_methods_failure(self):
        response = self.client.get(reverse("get_auth_methods"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_generate_auth_otp_success(self):
        with patch('custom.abdm.milestone_one.views.abha_verification_views.abdm_util.get_response_http_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("generate_auth_otp"),
                                        {"health_id": "123456", "auth_method": "MOBILE_OTP"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"txnId": "1234"})

    def test_generate_auth_otp_failure(self):
        response = self.client.post(reverse("generate_auth_otp"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_confirm_with_mobile_otp_success(self):
        with patch('custom.abdm.milestone_one.views.abha_verification_views.abdm_util.get_response_http_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("confirm_with_mobile_otp"),
                                        {"txn_id": "123456", "otp": "1111"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"txnId": "1234"})

    def test_confirm_with_mobile_otp_failure(self):
        response = self.client.post(reverse("confirm_with_mobile_otp"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_confirm_with_aadhaar_otp_success(self):
        with patch('custom.abdm.milestone_one.views.abha_verification_views.abdm_util.get_response_http_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("confirm_with_aadhaar_otp"),
                                        {"txn_id": "123456", "otp": "1111"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"txnId": "1234"})

    def test_confirm_with_aadhaar_otp_failure(self):
        response = self.client.post(reverse("confirm_with_aadhaar_otp"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_search_health_id_success(self):
        with patch('custom.abdm.milestone_one.views.abha_verification_views.abdm_util.get_response_http_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("search_health_id"), {"health_id": "11113333"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"authMethods": ["MOBILE_OTP"]})

    def test_search_health_id_failure(self):
        response = self.client.post(reverse("search_health_id"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    @override_settings(ABDM_CLIENT_ID='id', ABDM_CLIENT_SECRET='secret', ABDM_GATEWAY_URL='http://url.tld',
                       ABDM_ABHA_URL='http://base.tld')
    @patch('custom.abdm.milestone_one.utils.abha_verification_util.requests.post')
    def test_get_health_card_success(self, post_mock):
        post_mock.return_value = Mock()
        post_mock.status_code = 200
        post_mock.content = b'image'
        with patch('custom.abdm.milestone_one.utils.abha_verification_util.requests.get',
                   side_effect=TestABHAVerification._get_health_card_mock_response):
            response = self.client.post(reverse("get_health_card_png"), {"user_token": "fake_token"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"health_card": "aW1hZ2U="})

    def test_get_health_card_failure(self):
        response = self.client.post(reverse("get_health_card_png"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def test_get_health_id_existence_check_success(self):
        with patch('custom.abdm.milestone_one.views.abha_verification_views.abdm_util.get_response_http_post',
                   side_effect=TestABHAVerification._mock_abdm_http_post):
            response = self.client.post(reverse("exists_by_health_id"), {"health_id": "user@abdm"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'health_id': 'user@abdm', 'exists': True})

    def test_get_health_id_existence_check_failure(self):
        response = self.client.post(reverse("exists_by_health_id"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    def tearDown(self) -> None:
        ABDMUser.objects.all().delete()
