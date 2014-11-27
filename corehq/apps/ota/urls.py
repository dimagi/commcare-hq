from django.conf.urls import url, patterns

urlpatterns = patterns('',
    url(r'^restore/$', 'corehq.apps.ota.views.restore'),
)
