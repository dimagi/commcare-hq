from corehq.apps.document_templates.views import DocumentTemplatesView
from django.urls import path

urlpatterns = [
    path('templates/', DocumentTemplatesView.as_view(), name=DocumentTemplatesView.urlname),
]
