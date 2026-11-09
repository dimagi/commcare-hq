from django.urls import path

from corehq.apps.document_templates.views import (
    DeleteDocumentTemplateView,
    DocumentTemplatesView,
    EditDocumentTemplateView,
    NewDocumentTemplateView,
    preview_document,
    render_document,
    upload_area_image,
    preview_document_variables,
)

urlpatterns = [
    path('templates/', DocumentTemplatesView.as_view(), name=DocumentTemplatesView.urlname),
    path('templates/new', NewDocumentTemplateView.as_view(), name=NewDocumentTemplateView.urlname),
    path(
        'templates/<int:pk>/',
        EditDocumentTemplateView.as_view(),
        name=EditDocumentTemplateView.urlname,
    ),
    path(
        'templates/<int:pk>/delete/',
        DeleteDocumentTemplateView.as_view(),
        name=DeleteDocumentTemplateView.urlname,
    ),
    path('templates/preview/variables/', preview_document_variables, name='preview_document_variables'),
    path('templates/preview/', preview_document, name='preview_document'),
    path('templates/render', render_document, name='render_document'),
    path('templates/images/<str:area>/', upload_area_image, name='upload_document_template_image'),
]
