from django.conf.urls import url

from corehq.apps.cowin.views import find_appointment_by_pincode

urlpatterns = [
    url(r'^find_appointment_by_pincode/$', find_appointment_by_pincode, name='find_appointment_by_pincode'),
]
