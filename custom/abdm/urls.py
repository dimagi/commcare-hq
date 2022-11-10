from django.urls import path
from custom.abdm.milestone_one.views import abha_creation_views, abha_verification_views

abha_creation_urls = [
    path('api/generate_aadhaar_otp', abha_creation_views.generate_aadhaar_otp),
    path('api/generate_mobile_otp', abha_creation_views.generate_mobile_otp),
    path('api/verify_aadhaar_otp', abha_creation_views.verify_aadhaar_otp),
    path('api/verify_mobile_otp', abha_creation_views.verify_mobile_otp),
]

abha_verification_urls = [
    path('api/get_auth_methods', abha_verification_views.get_auth_methods),
    path('api/generate_auth_otp', abha_verification_views.generate_auth_otp),
    path('api/confirm_with_mobile_otp', abha_verification_views.confirm_with_mobile_otp),
    path('api/confirm_with_aadhaar_otp', abha_verification_views.confirm_with_aadhaar_otp),
    path('api/search_health_id', abha_verification_views.search_health_id),
]

urlpatterns = abha_creation_urls + abha_verification_urls
