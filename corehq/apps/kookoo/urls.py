from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.kookoo.views',
    url(r'^ivr/?$', 'ivr', name='ivr'),
    url(r'^ivr_finished/?$', 'ivr_finished', name='ivr_finished'),
)
