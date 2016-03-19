from django.conf.urls import *
from corehq.apps.domain.views import PublicSMSRatesView
from corehq.apps.settings.views import (
    TwoFactorProfileView, TwoFactorSetupView, TwoFactorSetupCompleteView,
    TwoFactorBackupTokensView, TwoFactorDisableView, TwoFactorPhoneSetupView,
    NewPhoneView
)
from two_factor.urls import urlpatterns as tf_urls
from two_factor.gateways.twilio.urls import urlpatterns as tf_twilio_urls
from corehq.apps.hqwebapp.views import MaintenanceAlertsView

urlpatterns = patterns(
    'corehq.apps.hqwebapp.views',
    (r'^$', 'redirect_to_default'),
    url(r'^homepage/$', 'redirect_to_default', name='homepage'),
    url(r'^default_landing/$', 'landing_page', name='landing_page'),
    url(r'^crossdomain.xml$', 'yui_crossdomain', name='yui_crossdomain'),
    (r'^serverup.txt$', 'server_up'),
    url(r'^change_password/$', 'password_change', name='password_change'),

    url(r'^no_permissions/$', 'no_permissions', name='no_permissions'),

    url(r'^accounts/login/(?P<domain_type>\w+)?$', 'login', name="login"),
    url(r'^accounts/logout/$', 'logout', name="logout"),
    (r'^reports/$', 'redirect_to_default'),
    url(r'^bug_report/$', 'bug_report', name='bug_report'),
    url(r'^debug/notify/$', 'debug_notify', name='debug_notify'),
    url(r'^search/$', 'quick_find', name="global_quick_find"),
    url(r'^searchDescription.xml$', 'osdd', name="osdd"),
    url(r'^messaging-pricing', PublicSMSRatesView.as_view(), name=PublicSMSRatesView.urlname),
    url(r'^alerts/$', MaintenanceAlertsView.as_view(), name=MaintenanceAlertsView.urlname),
    url(r'^create_alert/$', 'create_alert', name='create_alert'),
    url(r'^activate_alert/$', 'activate_alert', name='activate_alert'),
    url(r'^deactivate_alert/$', 'deactivate_alert', name='deactivate_alert'),
    url(r'^jserror/$', 'jserror', name='jserror'),
    url(r'^dropbox_upload/(?P<download_id>[0-9a-fA-Z]{25,32})/$', 'dropbox_upload',
        name='dropbox_upload'),
    url(r'^account/two_factor/$', TwoFactorProfileView.as_view(), name=TwoFactorProfileView.urlname),
    url(r'^account/two_factor/setup/$', TwoFactorSetupView.as_view(), name=TwoFactorSetupView.urlname),
    url(r'^account/two_factor/setup/complete/$', TwoFactorSetupCompleteView.as_view(), name=TwoFactorSetupCompleteView.urlname),
    url(r'^account/two_factor/backup/tokens/$', TwoFactorBackupTokensView.as_view(), name=TwoFactorBackupTokensView.urlname),
    url(r'^account/two_factor/disable/$', TwoFactorDisableView.as_view(), name=TwoFactorDisableView.urlname),
    url(r'^account/two_factor/backup/phone/register/$', TwoFactorPhoneSetupView.as_view(), name=TwoFactorPhoneSetupView.urlname),
    url(r'', include(tf_urls + tf_twilio_urls, 'two_factor')),
    url(r'^account/two_factor/new_phone/$', NewPhoneView.as_view(), name=NewPhoneView.urlname)
)

domain_specific = patterns('corehq.apps.hqwebapp.views',
    url(r'^$', 'redirect_to_default', name='domain_homepage'),
    url(r'^login/$', 'domain_login', name='domain_login'),
    url(r'^login/mobile/$', 'domain_login', name='domain_mobile_login',
        kwargs={'template_name': 'login_and_password/mobile_login.html'}),
    url(r'^retreive_download/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        'retrieve_download', {'template': 'style/includes/file_download.html'},
        name='hq_soil_download'),
    url(r'toggles.js$', 'toggles_js', name='toggles_js'),
)
