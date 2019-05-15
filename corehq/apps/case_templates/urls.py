from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.case_templates.views import create_template_view, CaseTemplatesListView

urlpatterns = [
    url(r'^create/$', create_template_view, name='create_case_template'),
    url(r'^list/$', CaseTemplatesListView.as_view(), name=CaseTemplatesListView.urlname),
]
