from django.conf.urls import include, re_path as url

from two_factor.gateways.twilio.urls import urlpatterns as tf_twilio_urls
from two_factor.urls import urlpatterns as tf_urls

from corehq.apps.cloudcare.views import session_endpoint
from corehq.apps.domain.views.sms import PublicSMSRatesView
from corehq.apps.hqwebapp.session_details_endpoint.views import (
    SessionDetailsView,
)
from corehq.apps.hqwebapp.views import (
    BugReportView,
    SolutionsFeatureRequestView,
    MaintenanceAlertsView,
    create_alert,
    debug_notify,
    domain_login,
    dropbox_upload,
    iframe_domain_login,
    domain_login_new_window,
    iframe_sso_login_pending,
    jserror,
    log_email_event,
    login,
    login_new_window,
    logout,
    no_permissions,
    osdd,
    password_change,
    ping_response,
    quick_find,
    redirect_to_default,
    redirect_to_dimagi,
    OauthApplicationRegistration,
    retrieve_download,
    server_up,
    temporary_google_verify,
    check_sso_login_status,
)
from corehq.apps.settings.views import (
    TwoFactorBackupTokensView,
    TwoFactorDisableView,
    TwoFactorPhoneDeleteView,
    TwoFactorPhoneSetupView,
    TwoFactorProfileView,
    TwoFactorResetView,
    TwoFactorSetupCompleteView,
    TwoFactorSetupView,
)


urlpatterns = [
    url(r'^$', redirect_to_default),
    url(r'^homepage/$', redirect_to_default, name='homepage'),
    url(r'^serverup.txt$', server_up),
    url(r'^change_password/$', password_change, name='password_change'),

    url(r'^no_permissions/$', no_permissions, name='no_permissions'),

    url(r'^accounts/login/$', login, name="login"),
    url(r'^accounts/logout/$', logout, name="logout"),
    url(r'^reports/$', redirect_to_default),
    url(r'^bug_report/$', BugReportView.as_view(), name='bug_report'),
    url(r'^solutions_feature_request/$', SolutionsFeatureRequestView.as_view(),
        name=SolutionsFeatureRequestView.urlname),
    url(r'^debug/notify/$', debug_notify, name='debug_notify'),
    url(r'^search/$', quick_find, name="global_quick_find"),
    url(r'^searchDescription.xml$', osdd, name="osdd"),
    url(r'^messaging-pricing', PublicSMSRatesView.as_view(), name=PublicSMSRatesView.urlname),
    url(r'^alerts/$', MaintenanceAlertsView.as_view(), name=MaintenanceAlertsView.urlname),
    url(r'^create_alert/$', create_alert, name='create_alert'),
    url(r'^jserror/$', jserror, name='jserror'),
    url(r'^dropbox_upload/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$', dropbox_upload,
        name='dropbox_upload'),
    url(r'^account/two_factor/$', TwoFactorProfileView.as_view(), name=TwoFactorProfileView.urlname),
    url(r'^account/two_factor/setup/$', TwoFactorSetupView.as_view(), name=TwoFactorSetupView.urlname),
    url(r'^account/two_factor/setup/complete/$', TwoFactorSetupCompleteView.as_view(),
        name=TwoFactorSetupCompleteView.urlname),
    url(r'^account/two_factor/backup/tokens/$', TwoFactorBackupTokensView.as_view(),
        name=TwoFactorBackupTokensView.urlname),
    url(r'^account/two_factor/disable/$', TwoFactorDisableView.as_view(), name=TwoFactorDisableView.urlname),
    url(r'^account/two_factor/phone/register/$', TwoFactorPhoneSetupView.as_view(),
        name=TwoFactorPhoneSetupView.urlname),
    url(r'^account/two_factor/phone/unregister/(?P<pk>\d+)/$', TwoFactorPhoneDeleteView.as_view(),
        name=TwoFactorPhoneDeleteView.urlname),
    url(r'', include(tf_urls)),
    url(r'', include(tf_twilio_urls)),
    url(r'^account/two_factor/reset/$', TwoFactorResetView.as_view(), name=TwoFactorResetView.urlname),
    url(r'^hq/admin/session_details/$', SessionDetailsView.as_view(),
        name=SessionDetailsView.urlname),
    url(r'^ping_login/$', ping_response, name='ping_login'),
    url(r'^ping_session/$', ping_response, name='ping_session'),
    url(r'^relogin/$', login_new_window, name='login_new_window'),
    url(r'^relogin/iframe/$', domain_login_new_window, name='domain_login_new_window'),
    url(r'^relogin/sso/$', iframe_sso_login_pending, name='iframe_sso_login_pending'),
    url(r'^log_email_event/(?P<secret>[\w]+)/?$', log_email_event, name='log_email_event'),
    url(r'^log_email_event/(?P<secret>[\w]+)/(?P<domain>[\w\.:-]+)/?$', log_email_event,
        name='log_domain_email_event'),
    url(
        r'^oauth/applications/register/',
        OauthApplicationRegistration.as_view(),
        name=OauthApplicationRegistration.urlname
    ),
    url(r'^oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    url(r'^check_sso_login_status/', check_sso_login_status, name='check_sso_login_status'),
]

domain_specific = [
    url(r'^$', redirect_to_default, name='domain_homepage'),
    url(r'^login/$', domain_login, name='domain_login'),
    url(r'^login/iframe/$', iframe_domain_login, name='iframe_domain_login'),
    url(r'^retreive_download/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        retrieve_download, {'template': 'hqwebapp/includes/bootstrap3/file_download.html'},
        name='hq_soil_download'),
    url(r'^app/v1/(?P<app_id>[\w-]+)/(?P<endpoint_id>[\w_-]+)/$', session_endpoint, name='session_endpoint'),
    url(r'^app/v1/(?P<app_id>[\w-]+)/$', session_endpoint, name='session_endpoint'),
]

prelogin_root = [
    url(r'^home/$', redirect_to_dimagi('commcare/'),
        name='public_home'),
    url(r'^impact/$', redirect_to_dimagi('commcare/'),
        name='public_impact'),
    url(r'^pricing/$', redirect_to_dimagi('commcare/pricing/'),
        name='public_software_services'),
    url(r'^software_services/$', redirect_to_dimagi('commcare/pricing/')),
    url(r'^services/$', redirect_to_dimagi('services/'),
        name='public_services'),
    url(r'^software/$', redirect_to_dimagi('commcare/pricing/'),
        name='public_pricing'),
    url(r'^solutions/$', redirect_to_dimagi('services/'),
        name='public_services'),
    url(r'^askdemo/$', redirect_to_dimagi('commcare/'),
        name='public_demo_cta'),
    url(r'^supply/$', redirect_to_dimagi('commcare/')),
]

legacy_prelogin = prelogin_root + [
    url(r'^google9633af922b8b0064.html$', temporary_google_verify),
    url(r'^lang/(?P<lang_code>[\w-]+)/', include(prelogin_root)),
]
