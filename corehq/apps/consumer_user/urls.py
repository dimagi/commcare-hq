from django.urls import path
from .views import login_view, register_view, success_view, logout_view, change_password_view, \
    domains_and_cases_list_view, change_contact_details_view

app_name = 'consumer_user'

urlpatterns = [
    path('signup/<invitation>/', register_view, name='patient_register'),
    path('login/', login_view, name='patient_login'),
    path('login/<invitation>/', login_view, name='patient_login_with_invitation'),
    path('logout/', logout_view, name='patient_logout'),
    path('homepage/', success_view, name='patient_homepage'),
    path('change-password/', change_password_view, name='change_password'),
    path('domain-case-list/', domains_and_cases_list_view, name='domain_and_cases_list'),
    path('change-contact-details/', change_contact_details_view, name='change_contact_details'),
]
