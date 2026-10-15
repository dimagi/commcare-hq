from corehq.apps.document_templates.views import (
    DocumentTemplatesView,
    NewDocumentTemplateView,
    PreviewDocumentView,
    PreviewVariablesView,
)
from django.urls import path

urlpatterns = [
    path('templates/', DocumentTemplatesView.as_view(), name=DocumentTemplatesView.urlname),
    path('templates/new', NewDocumentTemplateView.as_view(), name=NewDocumentTemplateView.urlname),
    path(
        'templates/preview/variables/',
        PreviewVariablesView.as_view(),
        name=PreviewVariablesView.urlname,
    ),
    path('templates/preview/', PreviewDocumentView.as_view(), name=PreviewDocumentView.urlname),
]
