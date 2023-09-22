import time

import requests
from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from custom.abdm.auth import ABDMUserAuthentication
from custom.abdm.const import STATUS_ERROR, STATUS_SUCCESS
from custom.abdm.exceptions import (
    ABDMGatewayCallbackTimeout,
    ABDMGatewayError2,
    ABDMServiceUnavailable,
    generate_response_for_gateway_error
)
from custom.abdm.hip.const import GW_ADD_CARE_CONTEXTS_URL
from custom.abdm.hip.exceptions import HIPErrorResponseFormatter
from custom.abdm.hip.models import HIPLinkRequest, HIPCareContext
from custom.abdm.hip.serializers.care_contexts import (
    GatewayOnAddContextsSerializer,
    LinkCareContextSerializer,
)
from custom.abdm.hip.views.base import HIPBaseView, HIPGatewayBaseView
from custom.abdm.utils import GatewayRequestHelper
from rest_framework.exceptions import ValidationError
from django.db import transaction


# TODO For consent health period range, how do we verify dates as input is care context for health data


class LinkCareContext(HIPBaseView):
    authentication_classes = [ABDMUserAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        try:
            serializer = LinkCareContextSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            linked_care_contexts = self.check_for_linked_care_contexts(request.data)
            if linked_care_contexts:
                detail_message = f"{linked_care_contexts} are already linked."
                return HIPErrorResponseFormatter().generate_custom_error_response(error_code=3420,
                                                                                  details_message=detail_message)
            gateway_request_id = self.gateway_add_care_contexts(request.data)
            self.save_link_request(request.user, gateway_request_id, request.data)
            response_data = self.poll_for_response(gateway_request_id)
            return self.generate_response(response_data)
        except ABDMGatewayError2 as err:
            return generate_response_for_gateway_error(err.error)

    def check_for_linked_care_contexts(self, request_data):
        care_contexts_references = [care_context['referenceNumber']
                                    for care_context in request_data['patient']['careContexts']]
        linked_care_contexts = list(HIPCareContext.objects.
                                    filter(care_context_number__in=care_contexts_references,
                                           link_request__hip_id=request_data['hip_id'],
                                           link_request__patient_reference=
                                           request_data['patient']['referenceNumber'],
                                           link_request__status=STATUS_SUCCESS
                                           ).values_list('care_context_number', flat=True))
        return linked_care_contexts

    def gateway_add_care_contexts(self, request_data):
        payload = GatewayRequestHelper.common_request_data()
        payload['link'] = request_data
        try:
            GatewayRequestHelper().post(GW_ADD_CARE_CONTEXTS_URL, payload)
        except requests.Timeout:
            raise ABDMServiceUnavailable()
        except requests.HTTPError as err:
            error = GatewayRequestHelper.json_from_response(err.response).get('error')
            raise ABDMGatewayError2(error=error)
        return payload["requestId"]

    @transaction.atomic()
    def save_link_request(self, user, gateway_request_id, request_data):

        link_request = HIPLinkRequest.objects.create(user=user,
                                                     gateway_request_id=gateway_request_id,
                                                     hip_id=request_data['hip_id'],
                                                     patient_reference=request_data['patient']['referenceNumber']
                                                     )
        for care_context in request_data['patient']['careContexts']:
            HIPCareContext.objects.create(care_context_number=care_context['referenceNumber'],
                                          health_info_types=care_context['hiTypes'],
                                          link_request=link_request)
        return link_request

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
        return Response(status=200, data=response_data["acknowledgement"])


class GatewayOnAddContexts(HIPGatewayBaseView):

    def post(self, request, format=None):
        print("GatewayAuthOnInit", request.data)
        serializer = GatewayOnAddContextsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.process_request(request.data)
        return Response(status=HTTP_202_ACCEPTED)

    def update_linking_status(self, request_data):
        linking_request = HIPLinkRequest.objects.get(gateway_request_id=request_data['resp']['requestId'])
        if request_data.get('error'):
            linking_request.status = STATUS_ERROR
            linking_request.error = request_data['error']
        else:
            linking_request.status = STATUS_SUCCESS
        linking_request.save()

    def process_request(self, request_data):
        self.update_linking_status(request_data)
        cache_key = request_data['resp']['requestId']
        cache.set(cache_key, request_data, 30)
