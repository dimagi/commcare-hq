from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.receiver.views',
    url(r'^/?$', 'post', name='receiver_post'),
    # odk urls
    url(r'^/submission/?$',  'post', name="receiver_odk_post"),
    url(r'^/formList/$', 'form_list', name='form_list'),

)