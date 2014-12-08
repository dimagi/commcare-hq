from django.conf.urls import url, patterns


urlpatterns = patterns('corehq.apps.ota.views',
    url(r'^restore/$', 'restore'),
    url(r'^historical_forms/$', 'historical_forms'),
)
