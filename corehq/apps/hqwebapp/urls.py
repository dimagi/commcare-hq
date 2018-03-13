from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import include, url
from corehq.apps.domain.views import PublicSMSRatesView
from corehq.apps.settings.views import (
    TwoFactorProfileView, TwoFactorSetupView, TwoFactorSetupCompleteView,
    TwoFactorBackupTokensView, TwoFactorDisableView, TwoFactorPhoneSetupView,
    TwoFactorResetView, TwoFactorPhoneDeleteView
)
from two_factor.urls import urlpatterns as tf_urls
from two_factor.gateways.twilio.urls import urlpatterns as tf_twilio_urls
from corehq.apps.hqwebapp.views import (
    MaintenanceAlertsView, redirect_to_default,
    yui_crossdomain, password_change, no_permissions, login, logout, debug_notify,
    quick_find, osdd, create_alert, activate_alert, deactivate_alert, jserror, dropbox_upload, domain_login,
    assert_initial_page_data, retrieve_download, toggles_js, couch_doc_counts, server_up, BugReportView)
from corehq.apps.hqwebapp.session_details_endpoint.views import SessionDetailsView

urlpatterns = [
    url(r'^$', redirect_to_default),
    url(r'^homepage/$', redirect_to_default, name='homepage'),
    url(r'^crossdomain.xml$', yui_crossdomain, name='yui_crossdomain'),
    url(r'^serverup.txt$', server_up),
    url(r'^change_password/$', password_change, name='password_change'),

    url(r'^no_permissions/$', no_permissions, name='no_permissions'),

    url(r'^accounts/login/$', login, name="login"),
    url(r'^accounts/logout/$', logout, name="logout"),
    url(r'^reports/$', redirect_to_default),
    url(r'^bug_report/$', BugReportView.as_view(), name='bug_report'),
    url(r'^debug/notify/$', debug_notify, name='debug_notify'),
    url(r'^assert/initial_page_data/$', assert_initial_page_data, name='assert_initial_page_data'),
    url(r'^search/$', quick_find, name="global_quick_find"),
    url(r'^searchDescription.xml$', osdd, name="osdd"),
    url(r'^messaging-pricing', PublicSMSRatesView.as_view(), name=PublicSMSRatesView.urlname),
    url(r'^alerts/$', MaintenanceAlertsView.as_view(), name=MaintenanceAlertsView.urlname),
    url(r'^create_alert/$', create_alert, name='create_alert'),
    url(r'^activate_alert/$', activate_alert, name='activate_alert'),
    url(r'^deactivate_alert/$', deactivate_alert, name='deactivate_alert'),
    url(r'^jserror/$', jserror, name='jserror'),
    url(r'^dropbox_upload/(?P<download_id>[0-9a-fA-Z]{25,32})/$', dropbox_upload,
        name='dropbox_upload'),
    url(r'^account/two_factor/$', TwoFactorProfileView.as_view(), name=TwoFactorProfileView.urlname),
    url(r'^account/two_factor/setup/$', TwoFactorSetupView.as_view(), name=TwoFactorSetupView.urlname),
    url(r'^account/two_factor/setup/complete/$', TwoFactorSetupCompleteView.as_view(), name=TwoFactorSetupCompleteView.urlname),
    url(r'^account/two_factor/backup/tokens/$', TwoFactorBackupTokensView.as_view(), name=TwoFactorBackupTokensView.urlname),
    url(r'^account/two_factor/disable/$', TwoFactorDisableView.as_view(), name=TwoFactorDisableView.urlname),
    url(r'^account/two_factor/backup/phone/register/$', TwoFactorPhoneSetupView.as_view(), name=TwoFactorPhoneSetupView.urlname),
    url(r'^account/two_factor/backup/phone/unregister/(?P<pk>\d+)/$', TwoFactorPhoneDeleteView.as_view(),
        name=TwoFactorPhoneDeleteView.urlname),
    url(r'', include((tf_urls + tf_twilio_urls, 'two_factor'), namespace='two_factor')),
    url(r'^account/two_factor/reset/$', TwoFactorResetView.as_view(), name=TwoFactorResetView.urlname),
    url(r'^hq/admin/session_details/$', SessionDetailsView.as_view(),
        name=SessionDetailsView.urlname),

]

domain_specific = [
    url(r'^$', redirect_to_default, name='domain_homepage'),
    url(r'^login/$', domain_login, name='domain_login'),
    url(r'^retreive_download/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        retrieve_download, {'template': 'hqwebapp/includes/file_download.html'},
        name='hq_soil_download'),
    url(r'toggles.js$', toggles_js, name='toggles_js'),
    url(r'couch_doc_counts', couch_doc_counts),
]
