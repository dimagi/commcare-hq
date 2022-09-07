from django.urls import path
from custom.abdm.milestone_one.views import abha_creation_views

abha_creation_urls = [
    path('api/login', abha_creation_views.login),
    path('api/generate_aadhaar_otp', abha_creation_views.generate_aadhaar_otp),
    path('api/generate_mobile_otp', abha_creation_views.generate_mobile_otp),
    path('api/verify_aadhaar_otp', abha_creation_views.verify_aadhaar_otp),
    path('api/verify_mobile_otp', abha_creation_views.verify_mobile_otp),
]

abha_verification_urls = [
    path('api/generate_aadhaar_otp', abha_creation_views.generate_aadhaar_otp),
    path('api/generate_mobile_otp', abha_creation_views.generate_mobile_otp),
    path('api/verify_aadhaar_otp', abha_creation_views.verify_aadhaar_otp),
    path('api/verify_mobile_otp', abha_creation_views.verify_mobile_otp),
]

urlpatterns = abha_creation_urls
