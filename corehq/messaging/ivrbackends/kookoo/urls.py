from django.conf.urls import patterns, url

from corehq.messaging.ivrbackends.kookoo.views import ivr, ivr_finished

urlpatterns = patterns('corehq.messaging.ivrbackends.kookoo.views',
    url(r'^ivr/?$', ivr, name='ivr'),
    url(r'^ivr_finished/?$', ivr_finished, name='ivr_finished'),
)
