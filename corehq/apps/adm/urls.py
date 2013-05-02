from django.conf.urls.defaults import *
from corehq.apps.adm.dispatcher import ADMAdminInterfaceDispatcher, ADMSectionDispatcher
from corehq.apps.adm.views import ADMAdminCRUDFormView

adm_admin_interface_urls = patterns('corehq.apps.adm.views',
    url(r'^$', 'default_adm_admin', name="default_adm_admin_interface"),
    url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
        ADMAdminCRUDFormView.as_view(), name="adm_item_form"),
    ADMAdminInterfaceDispatcher.url_pattern(),
)

urlpatterns = patterns('corehq.apps.adm.views',
    url(r'^$', 'default_adm_report', name="default_adm_report"),
    ADMSectionDispatcher.url_pattern(),
)
