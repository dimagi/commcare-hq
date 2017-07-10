from django.conf import settings
from django.conf.urls import include, url
from django.contrib.auth.views import password_reset
from django.utils.translation import ugettext as _

from corehq.apps.domain.forms import HQSetPasswordForm
from corehq.apps.domain.views import PublicSMSRatesView, PasswordResetView
from corehq.apps.settings.views import (
    TwoFactorProfileView, TwoFactorSetupView, TwoFactorSetupCompleteView,
    TwoFactorBackupTokensView, TwoFactorDisableView, TwoFactorPhoneSetupView,
    NewPhoneView
)
from two_factor.urls import urlpatterns as tf_urls
from two_factor.gateways.twilio.urls import urlpatterns as tf_twilio_urls
from corehq.apps.hqwebapp.views import (
    MaintenanceAlertsView, redirect_to_default,
    yui_crossdomain, password_change, no_permissions, login, logout, bug_report, debug_notify,
    quick_find, osdd, create_alert, activate_alert, deactivate_alert, jserror, dropbox_upload, domain_login,
    retrieve_download, toggles_js, couch_doc_counts, server_up, domain_reset_pwd, domain_reset_pwd_complete)

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
    url(r'^bug_report/$', bug_report, name='bug_report'),
    url(r'^debug/notify/$', debug_notify, name='debug_notify'),
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
    url(r'', include((tf_urls + tf_twilio_urls, 'two_factor'), namespace='two_factor')),
    url(r'^account/two_factor/new_phone/$', NewPhoneView.as_view(), name=NewPhoneView.urlname)
]

domain_specific = [
    url(r'^$', redirect_to_default, name='domain_homepage'),
    url(r'^login/$', domain_login, name='domain_login'),
    url(r'^login/mobile/$', domain_login, name='domain_mobile_login',
        kwargs={'template_name': 'login_and_password/mobile_login.html'}),

    # This url is linked to from web login page
    url(r'^reset_pwd_email/$', password_reset,
        {'template_name': 'login_and_password/password_reset_form.html',
         'email_template_name': 'login_and_password/domain_reset_pwd_email.html',
         'from_email': settings.DEFAULT_FROM_EMAIL,
         'extra_context': {'current_page': {'page_name': _('Password Reset')}}},
        name='domain_reset_pwd_email'),
    # This url is linked to from mobile login page
    url(r'^reset_pwd_email/mobile/$', password_reset,
        {'template_name': 'login_and_password/mobile_password_reset_form.html',
         'email_template_name': 'login_and_password/domain_mobile_reset_pwd_email.html',
         'from_email': settings.DEFAULT_FROM_EMAIL,
         'extra_context': {'current_page': {'page_name': _('Password Reset')}}},
        name='domain_mobile_reset_pwd_email'),

    url(r'^reset_pwd/web/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$', domain_reset_pwd,
        name='domain_reset_pwd'),
    url(r'^reset_pwd/mobile/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$', domain_reset_pwd,
        {'template_name': 'login_and_password/domain_mobile_reset_pwd.html'},
        name='domain_mobile_reset_pwd'),

    url(r'^reset_pwd_confirm/web/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        PasswordResetView.as_view(),
        {'template_name': 'login_and_password/domain_reset_pwd_confirm.html',
         'set_password_form': HQSetPasswordForm,
         'extra_context': {'current_page': {'page_name': _('Password Reset Confirmation')}}},
        name='domain_reset_pwd_confirm'),
    url(r'^reset_pwd_confirm/mobile/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        PasswordResetView.as_view(),
        {'template_name': 'login_and_password/domain_mobile_reset_pwd_confirm.html',
         'set_password_form': HQSetPasswordForm,
         'extra_context': {'current_page': {'page_name': _('Password Reset Confirmation')}},
         'post_reset_redirect': 'domain_mobile_reset_pwd_complete'},
        name='domain_mobile_reset_pwd_confirm'),

    url(r'^reset_pwd_confirm/web/done/$', domain_reset_pwd_complete,
        {'template_name': 'login_and_password/domain_reset_pwd_complete.html',
         'extra_context': {'current_page': {'page_name': _('Password Reset Complete')}}},
        name='domain_reset_pwd_complete'),
    url(r'^reset_pwd_confirm/mobile/done/$', domain_reset_pwd_complete,
        {'template_name': 'login_and_password/domain_mobile_reset_pwd_complete.html',
         'extra_context': {'current_page': {'page_name': _('Password Reset Complete')}}},
        name='domain_mobile_reset_pwd_complete'),

    url(r'^retreive_download/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        retrieve_download, {'template': 'style/includes/file_download.html'},
        name='hq_soil_download'),
    url(r'toggles.js$', toggles_js, name='toggles_js'),
    url(r'couch_doc_counts', couch_doc_counts),
]
