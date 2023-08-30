from django.urls import path

from custom.abdm.const import GATEWAY_CALLBACK_URL_PREFIX
from custom.abdm.hip.views.consents import GatewayConsentRequestNotify
from custom.abdm.hip.views.health_information import GatewayHealthInformationRequest

hip_urls = [
    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consents/hip/notify', GatewayConsentRequestNotify.as_view(),
         name='gateway_consent_request_notify_hip'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/health-information/hip/request', GatewayHealthInformationRequest.as_view(),
         name='gateway_health_information_request_hip'),
]
