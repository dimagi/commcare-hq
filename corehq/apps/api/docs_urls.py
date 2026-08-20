from django.urls import path

from corehq.apps.api.docs_views import (
    api_docs_index,
    api_docs_page,
    api_spec,
)

urlpatterns = [
    path('docs/', api_docs_index, name='api_docs_index'),
    path('docs/<slug:slug>/openapi.json', api_spec, name='api_docs_spec'),
    path('docs/<slug:slug>/', api_docs_page, name='api_docs_page'),
    path('openapi.json', api_spec, name='api_openapi_spec'),
]
