from django.urls import path

from corehq.apps.document_templates.views import (
    DeleteDocumentTemplateView,
    DocumentTemplatesView,
    EditDocumentTemplateView,
    NewDocumentTemplateView,
    PreviewDocumentView,
    PreviewVariablesView,
)

urlpatterns = [
    path('templates/', DocumentTemplatesView.as_view(), name=DocumentTemplatesView.urlname),
    path('templates/new', NewDocumentTemplateView.as_view(), name=NewDocumentTemplateView.urlname),
    path(
        'templates/<int:template_id>/',
        EditDocumentTemplateView.as_view(),
        name=EditDocumentTemplateView.urlname,
    ),
    path(
        'templates/<int:template_id>/delete/',
        DeleteDocumentTemplateView.as_view(),
        name=DeleteDocumentTemplateView.urlname,
    ),
    path(
        'templates/preview/variables/',
        PreviewVariablesView.as_view(),
        name=PreviewVariablesView.urlname,
    ),
    path('templates/preview/', PreviewDocumentView.as_view(), name=PreviewDocumentView.urlname),
]
