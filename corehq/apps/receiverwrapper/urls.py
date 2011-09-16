from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.receiverwrapper.views',
    url(r'^/?$', 'post', name='receiver_post'),
    url(r'^/(?P<app_id>\w+)/$', 'post', name='receiver_post_with_app_id'),
    # odk urls
    url(r'^/submission/?$',  'post', name="receiver_odk_post"),
    url(r'^/formList/$', 'form_list', name='form_list'),

)