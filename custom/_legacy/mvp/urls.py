from django.conf.urls import patterns, url
from mvp.views import MVPIndicatorAdminCRUDFormView, MVPBulkCopyIndicatorsView

urlpatterns = patterns('mvp.views',
    url(r'^copy/(?P<indicator_type>[\w_]+)/$', MVPBulkCopyIndicatorsView.as_view(), name="mvp_indicator_bulk_copy"),
    url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
        MVPIndicatorAdminCRUDFormView.as_view(), name="mvp_indicator_def_form"),
)
