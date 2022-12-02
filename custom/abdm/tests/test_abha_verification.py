from unittest.mock import patch

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

    def test_hq_abdm_verification_urls_resolution(self):
        self.assertEqual("/abdm/api/get_auth_methods", reverse("get_auth_methods"))
        self.assertEqual("/abdm/api/generate_auth_otp", reverse("generate_auth_otp"))
        self.assertEqual("/abdm/api/confirm_with_mobile_otp", reverse("confirm_with_mobile_otp"))
        self.assertEqual("/abdm/api/confirm_with_aadhaar_otp", reverse("confirm_with_aadhaar_otp"))
        self.assertEqual("/abdm/api/search_health_id", reverse("search_health_id"))

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
        self.assertEqual(response.json(), {"auth_methods": ["MOBILE_OTP"]})

    def test_search_health_id_failure(self):
        response = self.client.post(reverse("search_health_id"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.invalid_req_msg, response.json().get("message"))

    @staticmethod
    def _mock_abdm_http_post(url, payload):
        abdm_txn_id_mock = {"txnId": "1234"}
        return {
            "v1/search/searchByHealthId": {"auth_methods": ["MOBILE_OTP"]},
            "v2/auth/init": abdm_txn_id_mock,
            "v1/auth/confirmWithMobileOTP": abdm_txn_id_mock,
            "v1/auth/confirmWithAadhaarOtp": abdm_txn_id_mock,
        }.get(url)

    def tearDown(self) -> None:
        ABDMUser.objects.all().delete()
