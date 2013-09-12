from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.grapevine.views',
    url(r'^sms/?$', 'sms_in', name='sms_in'),
)
