from django.conf.urls import *

urlpatterns = patterns('corehq.apps.megamobile.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
)
