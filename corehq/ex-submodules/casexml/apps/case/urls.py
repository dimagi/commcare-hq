from django.conf.urls import patterns, url
from .views import reference_case_attachment_view

urlpatterns = patterns('',
    url(r'^casexml/attachment/(?P<domain>[\w\.:-]+)/(?P<case_id>[\w\-]+)/(?P<attachment_id>.*)$',
        reference_case_attachment_view, name="api_case_attachment")
)

