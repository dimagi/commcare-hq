from django.conf.urls import patterns, url

from corehq.messaging.smsbackends.unicel.views import incoming

urlpatterns = patterns('',         
    url(r'^in/$', incoming),
)
