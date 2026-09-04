from django.urls import path

from corehq.apps.api.docs_views import api_docs, api_spec

urlpatterns = [
    path('', api_docs, name='api_docs'),
    path('openapi.yaml', api_spec, name='api_docs_spec'),
]
