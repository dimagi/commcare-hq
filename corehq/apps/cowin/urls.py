from django.conf.urls import url

from corehq.apps.cowin.views import find_cowin_appointments

urlpatterns = [
    url(r'^find_cowin_appointments/$', find_cowin_appointments, name='find_cowin_appointments'),
]
