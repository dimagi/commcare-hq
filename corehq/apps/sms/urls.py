from django.urls import include, re_path as url

from corehq.apps.sms.views import (
    AddDomainGatewayView,
    AddGlobalGatewayView,
    ChatLastReadMessage,
    ChatMessageHistory,
    ChatOverSMSView,
    ComposeMessageView,
    DomainSmsGatewayListView,
    EditDomainGatewayView,
    EditGlobalGatewayView,
    GlobalBackendMap,
    GlobalSmsGatewayListView,
    SMSLanguagesView,
    SMSSettingsView,
    SubscribeSMSView,
    TestSMSMessageView,
    WhatsAppTemplatesView,
    api_send_sms,
    chat,
    chat_contact_list,
    default,
    download_sms_translations,
    edit_sms_languages,
    send_to_recipients,
    upload_sms_translations,
)
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from corehq.messaging.smsbackends.telerivet.urls import \
    domain_specific as telerivet_urls

urlpatterns = [
    url(r'^$', default, name='sms_default'),
    url(r'^send_to_recipients/$', send_to_recipients, name='send_to_recipients'),
    url(r'^compose/$', ComposeMessageView.as_view(), name=ComposeMessageView.urlname),
    url(r'^message_test/$', TestSMSMessageView.as_view(), name=TestSMSMessageView.urlname),
    url(r'^api/send_sms/$', api_send_sms, name='api_send_sms'),
    url(
        r"^add_gateway/(?P<hq_api_id>[\w-]+)/$", AddDomainGatewayView.as_view(), name=AddDomainGatewayView.urlname
    ),
    url(
        r"^edit_gateway/(?P<hq_api_id>[\w-]+)/(?P<backend_id>[\w-]+)/$",
        EditDomainGatewayView.as_view(),
        name=EditDomainGatewayView.urlname,
    ),
    url(r'^gateways/$', DomainSmsGatewayListView.as_view(), name=DomainSmsGatewayListView.urlname),
    url(r'^chat_contacts/$', ChatOverSMSView.as_view(), name=ChatOverSMSView.urlname),
    url(r'^chat_contact_list/$', chat_contact_list, name='chat_contact_list'),
    url(r'^chat/(?P<contact_id>[\w-]+)/(?P<vn_id>[\w-]+)/$', chat, name='sms_chat'),
    url(r'^chat/(?P<contact_id>[\w-]+)/?$', chat, name='sms_chat'),
    url(r'^api/history/$', ChatMessageHistory.as_view(), name=ChatMessageHistory.urlname),
    url(r'^api/last_read_message/$', ChatLastReadMessage.as_view(), name=ChatLastReadMessage.urlname),
    url(r'^settings/$', SMSSettingsView.as_view(), name=SMSSettingsView.urlname),
    url(r'^subscribe_sms/$', SubscribeSMSView.as_view(), name=SubscribeSMSView.urlname),
    url(r'^languages/$', SMSLanguagesView.as_view(), name=SMSLanguagesView.urlname),
    url(r'^languages/edit/$', edit_sms_languages, name='edit_sms_languages'),
    url(r'^translations/download/$', download_sms_translations, name='download_sms_translations'),
    url(r'^translations/upload/$', upload_sms_translations, name='upload_sms_translations'),
    url(r'^telerivet/', include(telerivet_urls)),
    url(r'^whatsapp_templates/$', WhatsAppTemplatesView.as_view(), name=WhatsAppTemplatesView.urlname),
]


sms_admin_interface_urls = [
    url(r'^$', GlobalSmsGatewayListView.as_view(), name='default_sms_admin_interface'),
    url(r'^global_gateways/$', GlobalSmsGatewayListView.as_view(), name=GlobalSmsGatewayListView.urlname),
    url(r'^add_global_gateway/(?P<hq_api_id>[\w-]+)/$', AddGlobalGatewayView.as_view(),
        name=AddGlobalGatewayView.urlname),
    url(r'^edit_global_gateway/(?P<hq_api_id>[\w-]+)/(?P<backend_id>[\w-]+)/$',
        EditGlobalGatewayView.as_view(), name=EditGlobalGatewayView.urlname),
    url(r'^global_backend_map/$', GlobalBackendMap.as_view(), name=GlobalBackendMap.urlname),
    url(SMSAdminInterfaceDispatcher.pattern(), SMSAdminInterfaceDispatcher.as_view(),
        name=SMSAdminInterfaceDispatcher.name()),
]
