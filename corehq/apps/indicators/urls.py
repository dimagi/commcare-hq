from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url
from corehq.apps.indicators.dispatcher import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.views import (
    IndicatorAdminCRUDFormView,
    BulkCopyIndicatorsView,
    BulkExportIndicatorsView,
    BulkImportIndicatorsView,
    default_admin,
)

urlpatterns = [
   url(r'^$', default_admin, name="default_indicator_admin"),
   url(r'^export/$', BulkExportIndicatorsView.as_view(),
       name=BulkExportIndicatorsView.urlname),
   url(r'^import/$', BulkImportIndicatorsView.as_view(),
       name=BulkImportIndicatorsView.urlname),
   url(r'^copy/(?P<indicator_type>[\w_]+)/$', BulkCopyIndicatorsView.as_view(), name="indicator_bulk_copy"),
   url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
       IndicatorAdminCRUDFormView.as_view(), name="indicator_def_form"),
   IndicatorAdminInterfaceDispatcher.url_pattern(),
]
