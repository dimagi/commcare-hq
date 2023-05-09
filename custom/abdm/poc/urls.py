from django.urls import path

from custom.abdm.poc.hip.views import (
    patient_profile_share,
    care_context_discover,
    care_context_link_init,
    care_context_link_confirm,
    consent_notification,
    health_info_request,
)
from custom.abdm.poc.hiu.views import (
    consent_requests_on_init,
    consent_requests_on_status,
    consents_hiu_notify,
    consents_on_fetch,
    generate_consent_request,
    fetch_consents,
    health_info_on_request,
    health_data_receiver,
    request_health_info
)

hip_urls = [
    # Below API to be called by the gateway
    path('v1.0/patients/profile/share', patient_profile_share, name='patient_profile_share'),
    path('v0.5/care-contexts/discover', care_context_discover, name='care_context_discover'),
    path('v0.5/links/link/init', care_context_link_init, name='care_context_link_init'),
    path('v0.5/links/link/confirm', care_context_link_confirm, name='care_context_link_confirm'),
    path('v0.5/consents/hip/notify', consent_notification, name='consent_notification'),
    path('v0.5/health-information/hip/request', health_info_request, name='health_info_request'),
]

hiu_urls = [
    # Below API to be called by the gateway
    path('v0.5/consent-requests/on-init', consent_requests_on_init, name='consent_requests_on_init'),
    path('v0.5/consent-requests/on-status', consent_requests_on_status, name='consent_requests_on_status'),
    path('v0.5/consents/hiu/notify', consents_hiu_notify, name='consents_hiu_notify'),
    path('v0.5/consents/on-fetch', consents_on_fetch, name='consents_on_fetch'),
    path('v0.5/health-information/hiu/on-request', health_info_on_request, name='health_info_on_request'),
    path('v0.5/health-information/transfer', health_data_receiver, name='health_data_receiver'),
    # Trigger consents and health info request
    path('hiu/generate_consent_request', generate_consent_request, name='generate_consent_request'),
    path('hiu/fetch_consents', fetch_consents, name='fetch_consents'),
    path('hiu/request_health_info', request_health_info, name='request_health_info'),
]
