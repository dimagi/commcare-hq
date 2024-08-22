from django.urls import re_path as url
from .views import (
    ODataCaseMetadataView,
    ODataCaseServiceView,
    ODataFormMetadataView,
    ODataFormServiceView,
)

urlpatterns = [
    url(r'cases/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/$',
        ODataCaseServiceView.as_view(), name=ODataCaseServiceView.table_urlname),
    url(r'cases/(?P<config_id>[\w\-:]+)/$',
        ODataCaseServiceView.as_view(), name=ODataCaseServiceView.urlname),
    url(r'cases/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/\$metadata$',
        ODataCaseMetadataView.as_view(), name=ODataCaseMetadataView.table_urlname),
    url(r'cases/(?P<config_id>[\w\-:]+)/\$metadata$',
        ODataCaseMetadataView.as_view(), name=ODataCaseMetadataView.urlname),

    url(r'forms/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/$',
        ODataFormServiceView.as_view(), name=ODataFormServiceView.table_urlname),
    url(r'forms/(?P<config_id>[\w\-:]+)/$',
        ODataFormServiceView.as_view(), name=ODataFormServiceView.urlname),
    url(r'forms/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/\$metadata$',
        ODataFormMetadataView.as_view(), name=ODataFormMetadataView.table_urlname),
    url(r'forms/(?P<config_id>[\w\-:]+)/\$metadata$',
        ODataFormMetadataView.as_view(), name=ODataFormMetadataView.urlname),
]
