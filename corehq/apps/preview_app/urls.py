from django.conf.urls import patterns, url

from corehq.apps.preview_app.views import PreviewAppView


urlpatterns = patterns('corehq.apps.preview_app.views',
    url(r'^(?P<app_id>[\w-]+)/$', PreviewAppView.as_view(), name=PreviewAppView.urlname),
)
