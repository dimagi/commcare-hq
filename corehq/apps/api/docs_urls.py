from django.urls import path

from corehq.apps.api.docs_views import api_spec

urlpatterns = [
    path('docs/<slug:slug>/openapi.json', api_spec, name='api_docs_spec'),
    path('openapi.json', api_spec, name='api_openapi_spec'),
]
