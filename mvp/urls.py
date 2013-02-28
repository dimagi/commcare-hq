from django.conf.urls.defaults import patterns, url
from mvp.views import MVPIndicatorAdminCRUDFormView

urlpatterns = patterns('mvp.views',
                       url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
                           MVPIndicatorAdminCRUDFormView.as_view(), name="mvp_indicator_def_form"),
                       )
