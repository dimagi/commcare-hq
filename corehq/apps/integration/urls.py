from django.urls import re_path as url

from corehq.apps.integration.views import BiometricIntegrationView
from corehq.apps.reports.views import (
    TableauServerView,
    TableauVisualizationListView,
    TableauVisualizationDetailView,
)

settings_patterns = [
    url(r'^biometric/$', BiometricIntegrationView.as_view(),
        name=BiometricIntegrationView.urlname),
    url(r'^tableau_server/$', TableauServerView.as_view(), name=TableauServerView.urlname),
    url(r'^tableau_visualization/$', TableauVisualizationListView.as_view(),
        name=TableauVisualizationListView.urlname),
    url(r'^tableau_visualization/(?P<pk>\d+)/$', TableauVisualizationDetailView.as_view(),
        name=TableauVisualizationDetailView.urlname),
    url(r'^tableau_visualization/add/$', TableauVisualizationDetailView.as_view(),
        name=TableauVisualizationDetailView.urlname),
]

urlpatterns = []
