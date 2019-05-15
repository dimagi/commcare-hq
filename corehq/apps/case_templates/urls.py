from __future__ import absolute_import, unicode_literals

from django.conf.urls import url

from corehq.apps.case_templates.views import (
    CaseTemplatesListView,
    create_instance_view,
    create_template_view,
    delete_template_view,
)

urlpatterns = [
    url(r'^create/$', create_template_view, name='create_case_template'),
    url(r'^list/$', CaseTemplatesListView.as_view(), name=CaseTemplatesListView.urlname),
    url(r'^create_instance/$', create_instance_view, name='create_template_instance'),
    url(r'^delete/$', delete_template_view, name='delete_template'),
]
