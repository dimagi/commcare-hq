from django.conf.urls import patterns, url

urlpatterns = patterns('corehq.messaging.ivrbackends.kookoo.views',
    url(r'^ivr/?$', 'ivr', name='ivr'),
    url(r'^ivr_finished/?$', 'ivr_finished', name='ivr_finished'),
)
