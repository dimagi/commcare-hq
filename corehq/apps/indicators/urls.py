from django.conf.urls.defaults import patterns, url
from corehq import IndicatorAdminInterfaceDispatcher
from corehq.apps.indicators.views import (
    IndicatorAdminCRUDFormView,
    BulkCopyIndicatorsView,
    BulkExportIndicatorsView,
    BulkImportIndicatorsView,
)

urlpatterns = patterns('corehq.apps.indicators.views',
   url(r'^$', 'default_admin', name="default_indicator_admin"),
   url(r'^export/$', BulkExportIndicatorsView.as_view(),
       name=BulkExportIndicatorsView.urlname),
   url(r'^import/$', BulkImportIndicatorsView.as_view(),
       name=BulkImportIndicatorsView.urlname),
   url(r'^copy/(?P<indicator_type>[\w_]+)/$', BulkCopyIndicatorsView.as_view(), name="indicator_bulk_copy"),
   url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
       IndicatorAdminCRUDFormView.as_view(), name="indicator_def_form"),
   IndicatorAdminInterfaceDispatcher.url_pattern(),
)

