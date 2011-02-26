from django.conf.urls.defaults import *

urlpatterns = patterns('receiver.views',
    url(r'^/?$', 'post', name='receiver_post'),
    url(r'^/home/$', 'home', name='receiver_home'),
    # odk urls
    url(r'^/submission/?$',  'post', name="receiver_odk_post"),
    url(r'^/formList/$', 'form_list', name='form_list'),

)