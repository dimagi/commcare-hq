from django.urls import path

from .views import login_view, register_view, success_view, logout_view

app_name = 'consumer_user'

urlpatterns = [
    path('signup/<invitation>/', register_view, name='patient_register'),
    path('login/', login_view, name='patient_login'),
    path('logout/', logout_view, name='patient_logout'),
    path('homepage/', success_view, name='patient_homepage'),
]
