import time

import requests
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.const import AuthenticationMode
from custom.abdm.exceptions import (
    ABDMGatewayCallbackTimeout,
    ABDMGatewayError2,
    ABDMServiceUnavailable, generate_response_for_gateway_error,
)
from custom.abdm.user_auth.const import (
    GW_AUTH_CONFIRM_PATH,
    GW_AUTH_INIT_PATH,
    GW_FETCH_AUTH_MODES_PATH,
)
from custom.abdm.user_auth.exceptions import (
    user_auth_exception_handler,
    user_auth_gateway_exception_handler,
)
from custom.abdm.user_auth.serializers import (
    AuthConfirmSerializer,
    AuthFetchModesSerializer,
    AuthInitSerializer,
    GatewayAuthOnConfirmSerializer,
    GatewayAuthOnFetchModesSerializer,
    GatewayAuthOnInitSerializer,
)
from custom.abdm.utils import GatewayRequestHelper


# NOTE: 2 types of gateway error: One from initial request, other from callback response


class UserAuthBaseView(APIView):

    def get_exception_handler(self):
        return user_auth_exception_handler


class UserAuthGatewayBaseView(APIView):

    def get_exception_handler(self):
        return user_auth_gateway_exception_handler


class AuthFetchModes(UserAuthBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        try:
            serializer = AuthFetchModesSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            # TODO (Optional Add Check for existing ABHA ID here)
            gateway_request_id = self.gateway_auth_fetch_modes(serializer.data)
            response_data = self.poll_for_response(gateway_request_id)
            return self.generate_response(response_data)
        except ABDMGatewayError2 as err:
            return generate_response_for_gateway_error(err.error)

    def gateway_auth_fetch_modes(self, request_data):
        payload = GatewayRequestHelper.common_request_data()
        payload['query'] = request_data
        try:
            GatewayRequestHelper().post(GW_FETCH_AUTH_MODES_PATH, payload)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = GatewayRequestHelper.json_from_response(err.response).get('error')
            raise ABDMGatewayError2(error=error)
        return payload["requestId"]

    def poll_for_response(self, cache_key):
        # TODO Refine this or use a better approach of subscription if available in RabbitMQ
        # TODO For Cache Key, Maybe Add Prefix
        attempt = 0
        while attempt <= 20:
            print(f"Checking in cache for {cache_key}")
            data = cache.get(cache_key)
            if data:
                cache.delete(cache_key)
                return data
            time.sleep(2)
            attempt += 1
        return False

    def generate_response(self, response_data):
        if response_data is False:
            raise ABDMGatewayCallbackTimeout()
        if response_data.get('error'):
            raise ABDMGatewayError2(error=response_data['error'])
        # Authentication Mode DIRECT is not yet supported.
        if AuthenticationMode.DIRECT in response_data['auth']['modes']:
            response_data['auth']['modes'].remove(AuthenticationMode.DIRECT)
        return Response(status=200, data=response_data["auth"])


class GatewayAuthOnFetchModes(UserAuthGatewayBaseView):

    def post(self, request, format=None):
        print("GatewayAuthOnFetchModes", request.data)
        serializer = GatewayAuthOnFetchModesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.process_request(serializer.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        cache_key = request_data['resp']['requestId']
        cache.set(cache_key, request_data, 30)


class AuthInit(UserAuthBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        try:
            serializer = AuthInitSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            # TODO (Optional Add Check for existing ABHA ID here)
            gateway_request_id = self.gateway_auth_init(serializer.data)
            response_data = self.poll_for_response(gateway_request_id)
            return self.generate_response(response_data)
        except ABDMGatewayError2 as err:
            return generate_response_for_gateway_error(err.error)

    def gateway_auth_init(self, request_data):
        payload = GatewayRequestHelper.common_request_data()
        payload['query'] = request_data
        try:
            GatewayRequestHelper().post(GW_AUTH_INIT_PATH, payload)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = GatewayRequestHelper.json_from_response(err.response).get('error')
            raise ABDMGatewayError2(error=error)
        return payload["requestId"]

    def poll_for_response(self, cache_key):
        # TODO Refine this or use a better approach of subscription if available in RabbitMQ
        # TODO For Cache Key, Maybe Add Prefix
        attempt = 0
        while attempt <= 20:
            print(f"Checking in cache for {cache_key}")
            data = cache.get(cache_key)
            if data:
                cache.delete(cache_key)
                return data
            time.sleep(2)
            attempt += 1
        return False

    def generate_response(self, response_data):
        if response_data is False:
            raise ABDMGatewayCallbackTimeout()
        if response_data.get('error'):
            raise ABDMGatewayError2(error=response_data['error'])
        return Response(status=200, data=response_data["auth"])


class GatewayAuthOnInit(UserAuthGatewayBaseView):

    def post(self, request, format=None):
        print("GatewayAuthOnInit", request.data)
        serializer = GatewayAuthOnInitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.process_request(serializer.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        cache_key = request_data['resp']['requestId']
        cache.set(cache_key, request_data, 30)


class AuthConfirm(UserAuthBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        try:
            serializer = AuthConfirmSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            gateway_request_id = self.gateway_auth_confirm(serializer.data)
            response_data = self.poll_for_response(gateway_request_id)
            return self.generate_response(response_data)
        except ABDMGatewayError2 as err:
            return generate_response_for_gateway_error(err.error)

    def gateway_auth_confirm(self, request_data):
        payload = GatewayRequestHelper.common_request_data()
        payload['transactionId'] = request_data.pop('transactionId')
        payload['credential'] = request_data['credential']
        try:
            GatewayRequestHelper().post(GW_AUTH_CONFIRM_PATH, payload)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = GatewayRequestHelper.json_from_response(err.response).get('error')
            raise ABDMGatewayError2(error=error)
        return payload["requestId"]

    def poll_for_response(self, cache_key):
        # TODO Refine this or use a better approach of subscription if available in RabbitMQ
        # TODO For Cache Key, Maybe Add Prefix
        attempt = 0
        while attempt <= 20:
            print(f"Checking in cache for {cache_key}")
            data = cache.get(cache_key)
            if data:
                cache.delete(cache_key)
                return data
            time.sleep(2)
            attempt += 1
        return False

    def generate_response(self, response_data):
        if response_data is False:
            raise ABDMGatewayCallbackTimeout()
        if response_data.get('error'):
            raise ABDMGatewayError2(error=response_data['error'])
        return Response(status=200, data=response_data["auth"])


class GatewayAuthOnConfirm(UserAuthGatewayBaseView):

    def post(self, request, format=None):
        print("GatewayAuthOnConfirm", request.data)
        serializer = GatewayAuthOnConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.process_request(serializer.data)
        return Response(status=HTTP_202_ACCEPTED)

    def process_request(self, request_data):
        cache_key = request_data['resp']['requestId']
        cache.set(cache_key, request_data, 30)
