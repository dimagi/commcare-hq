from django.urls import path
from .views import generate_aadhaar_otp


urlpatterns = [
    path('api/generate_aadhaar_otp', generate_aadhaar_otp)
]
