from django.conf.urls import patterns, url
from corehq.apps.prototype.views.workflow_builder import WorflowBuilderView

workflow_builder_urls = patterns(
    'corehq.apps.prototype.views.workflow_builder',
    url(r'^$', WorflowBuilderView.as_view(), name=WorflowBuilderView.urlname),
)
