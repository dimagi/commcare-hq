from django.conf.urls import *

urlpatterns = patterns('custom.m4change.views',
    url(r'^update_service_status/$', 'update_service_status', name='update_service_status'),
)
