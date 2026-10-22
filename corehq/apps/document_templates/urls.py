from django.urls import path

from corehq.apps.document_templates.views import (
    DeleteDocumentTemplateView,
    DocumentTemplatesView,
    DownloadDocumentView,
    EditDocumentTemplateView,
    NewDocumentTemplateView,
    PreviewDocumentView,
    PreviewVariablesView,
    RenderDocumentView,
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
    path('templates/render', RenderDocumentView.as_view(), name=RenderDocumentView.urlname),
    path('templates/download', DownloadDocumentView.as_view(), name=DownloadDocumentView.urlname),
]
