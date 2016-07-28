from django.conf.urls import patterns, url, include
from corehq.apps.prototype.urls.workflow_builder import workflow_builder_urls

urlpatterns = patterns(
    '',
    url(r'^workflow/', include(workflow_builder_urls)),
)
