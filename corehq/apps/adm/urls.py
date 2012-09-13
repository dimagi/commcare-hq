from django.conf.urls.defaults import *
from corehq.apps.adm.dispatcher import ADMAdminInterfaceDispatcher, ADMSectionDispatcher

adm_admin_interface_urls = patterns('corehq.apps.adm.views',
    url(r'^form/(?P<form_type>[\w_]+)/(?P<action>[(update)|(new)|(delete)]+)/((?P<item_id>[\w_]+)/)?$',
        'adm_item_form', name="adm_item_form"),
    url(ADMAdminInterfaceDispatcher.pattern(), ADMAdminInterfaceDispatcher.as_view(),
        name=ADMAdminInterfaceDispatcher.name()
    )
)

urlpatterns = patterns('corehq.apps.adm.views',
    url(r'^$', 'default_adm_report', name="default_adm_report"),
    url(ADMSectionDispatcher.pattern(), ADMSectionDispatcher.as_view(),
        name=ADMSectionDispatcher.name()
    )
)