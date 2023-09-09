from unittest.mock import patch

from django.test.utils import override_settings
from django.urls import path
from drf_standardized_errors.handler import exception_handler as drf_standardized_exception_handler
from rest_framework import serializers
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from rest_framework.test import APITestCase
from rest_framework.views import APIView

from custom.abdm.exceptions import ABDMErrorResponseFormatter


class SampleErrorResponseFormatter(ABDMErrorResponseFormatter):
    error_code_prefix = '9'
    error_messages = {
        9400: "Required attributes not provided or Request information is not as expected",
        9401: "Unauthorized request",
        9404: "Resource not found",
        9500: "Unknown error occurred",
    }


def sample_exception_handler(exc, context):
    response = drf_standardized_exception_handler(exc, context)
    return SampleErrorResponseFormatter().format_drf_response(response)


class SampleAPIView(APIView):
    authentication_classes = [TokenAuthentication]

    def get_exception_handler(self):
        return sample_exception_handler

    def post(self, request, format=None):
        return Response({})


urlpatterns = [
    path('test/sample', SampleAPIView.as_view(), name='sample'),
]


@override_settings(
    ROOT_URLCONF='custom.abdm.tests.test_errors',
    DRF_STANDARDIZED_ERRORS={
        "ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS": True
    },
)
class TestAPIErrors(APITestCase):
    """Test that the error response obtained from ABDM APIs matches the desired format"""

    def _assert_code_message(self, json_resp, expected_error_code):
        self.assertEqual(json_resp['error']['code'], expected_error_code)
        self.assertEqual(json_resp['error']['message'],
                         SampleErrorResponseFormatter.error_messages[expected_error_code])

    @patch('custom.abdm.tests.test_errors.SampleAPIView.post',
           side_effect=serializers.ValidationError({'field1': 'This is required.'}))
    def test_400_error(self, mocked_object):
        res = self.client.post(reverse('sample'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 400)
        self._assert_code_message(json_resp, 9400)
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': 'invalid', 'detail': 'This is required.', 'attr': 'field1'})

    @patch('custom.abdm.tests.test_errors.SampleAPIView.post', side_effect=NotAuthenticated)
    def test_401_error(self, mocked_object):
        res = self.client.post(reverse('sample'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 401)
        self._assert_code_message(json_resp, 9401)
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': 'not_authenticated',
                          'detail': 'Authentication credentials were not provided.', 'attr': None})

    @patch('custom.abdm.tests.test_errors.SampleAPIView.post', side_effect=NotFound)
    def test_404_error(self, mocked_object):
        res = self.client.post(reverse('sample'))
        print("test_404_error", res.json())
        json_resp = res.json()
        self.assertEqual(res.status_code, 404)
        self._assert_code_message(json_resp, 9404)
        self.assertEqual(json_resp['error']['details'][0],
                         {'code': 'not_found', 'detail': 'Not found.', 'attr': None})

    @patch('custom.abdm.tests.test_errors.SampleAPIView.post', side_effect=Exception('Unhandled error'))
    def test_500_error(self, mocked_object):
        # Test Client catches unhandled error signal sent by drf_standardized_exception_handler and re raises it.
        client = APIClient(raise_request_exception=False)
        res = client.post(reverse('sample'))
        json_resp = res.json()
        self.assertEqual(res.status_code, 500)
        self._assert_code_message(json_resp, 9500)
        self.assertIsNone(json_resp['error'].get('details'))
