from django.urls import re_path as url

from .views import reference_case_attachment_view

urlpatterns = [
    url(r'^casexml/attachment/(?P<domain>[\w\.:-]+)/(?P<case_id>[\w\-]+)/(?P<attachment_id>.*)$',
        reference_case_attachment_view, name="api_case_attachment")
]
