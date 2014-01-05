from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.receiverwrapper.views',
    url(r'^/?$', 'post', name='receiver_post'),
    url(r'^/secure/(?P<app_id>[\w-]+)/$', 'secure_post', name='receiver_secure_post_with_app_id'),
    url(r'^/secure/$', 'secure_post', name='receiver_secure_post'),

    # odk urls
    url(r'^/submission/?$',  'post', name="receiver_odk_post"),
    url(r'^/(?P<app_id>[\w-]+)/$', 'post', name='receiver_post_with_app_id'),
)
