from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.sislog.views',
    url(r'^in/?$', 'sms_in', name='sms_in'),
)
