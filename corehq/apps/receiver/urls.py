from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.receiver.views',
    url(r'^$', 'post', name='receiver_post'),
    url(r'^submission/$',  'post', name="receiver_odk_post"),

)