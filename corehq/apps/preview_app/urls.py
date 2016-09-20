from django.conf.urls import url

from corehq.apps.preview_app.views import PreviewAppView


urlpatterns = [
    url(r'^(?P<app_id>[\w-]+)/$', PreviewAppView.as_view(), name=PreviewAppView.urlname),
]
