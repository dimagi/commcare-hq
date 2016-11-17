from django.conf.urls import url

from custom.m4change.views import update_service_status

urlpatterns = [
    url(r'^update_service_status/$', update_service_status, name='update_service_status'),
]
