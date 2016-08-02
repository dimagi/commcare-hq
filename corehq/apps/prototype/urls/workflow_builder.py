from django.conf.urls import patterns, url
from corehq.apps.prototype.views.workflow_builder import WorflowBuilderView, PromptView

workflow_builder_urls = patterns(
    'corehq.apps.prototype.views.workflow_builder',
    url(r'^$', WorflowBuilderView.as_view(), name=WorflowBuilderView.urlname),
    url(r'^prompt/$', PromptView.as_view(), name=PromptView.urlname),
)
