from django.urls import path

from .views import patient_profile_share, patient_care_context, consent_notification

hip_urls = [
    # Below API to be called by the gateway
    path('v1.0/patients/profile/share', patient_profile_share, name='patient_profile_share'),
    path('v0.5/care-contexts/discover', patient_care_context, name='patient_care_context'),
    path('v0.5/consents/hip/notify', consent_notification, name='consent_notification'),
]
