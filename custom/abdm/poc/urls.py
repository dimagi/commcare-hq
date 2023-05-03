from django.urls import path

from custom.abdm.poc.hip.views import (
    patient_profile_share,
    care_context_discover,
    care_context_link_init,
    care_context_link_confirm,
    consent_notification,
    health_info_request,
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
