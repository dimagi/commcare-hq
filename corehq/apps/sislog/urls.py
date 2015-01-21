from django.conf.urls import *

urlpatterns = patterns('corehq.apps.sislog.views',
    url(r'^in/?$', 'sms_in', name='sms_in'),
)
