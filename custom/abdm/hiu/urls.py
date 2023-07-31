from django.urls import path

from custom.abdm.const import GATEWAY_CALLBACK_URL_PREFIX
from custom.abdm.hiu.views.consents import (GenerateConsent,
                                            GatewayConsentRequestOnInit, GatewayConsentRequestNotify,
                                            GatewayConsentRequestOnFetch)

hiu_urls = [
    path('api/hiu/generate_consent_request', GenerateConsent.as_view(), name='generate_consent_request'),

    # APIS that will be triggered by ABDM Gateway
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consent-requests/on-init', GatewayConsentRequestOnInit.as_view(),
         name='gateway_consent_request_on_init'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consents/hiu/notify', GatewayConsentRequestNotify.as_view(),
         name='gateway_consent_request_notify'),
    path(f'{GATEWAY_CALLBACK_URL_PREFIX}/consents/on-fetch', GatewayConsentRequestOnFetch.as_view(),
         name='gateway_consent_request_on_fetch'),
]
