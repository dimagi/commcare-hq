from corehq.apps.document_templates.views import (
    DocumentTemplatesView,
    NewDocumentTemplateView
)
from django.urls import path

urlpatterns = [
    path('templates/', DocumentTemplatesView.as_view(), name=DocumentTemplatesView.urlname),
    path('templates/new', NewDocumentTemplateView.as_view(), name=NewDocumentTemplateView.urlname),
]
