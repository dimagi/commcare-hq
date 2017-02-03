from django.conf import settings
from django.conf.urls import url, include
from django.shortcuts import render
from django.views.generic import TemplateView, RedirectView

from corehq.apps.app_manager.views import download_test_jar
from corehq.apps.app_manager.views.formdesigner import ping
from corehq.apps.appstore.views import rewrite_url
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.utils import legacy_domain_re

from django.contrib import admin
from corehq.apps.domain.views import ProBonoStaticView, logo
from corehq.apps.hqwebapp.views import eula, apache_license, bsd_license, product_agreement, cda, unsubscribe
from corehq.apps.reports.views import ReportNotificationUnsubscribeView
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.reports.urls import report_urls
from corehq.apps.registration.utils import PRICING_LINK
from corehq.apps.sms.views import sms_in

try:
    from localsettings import LOCAL_APP_URLS
except ImportError:
    LOCAL_APP_URLS = []

try:
    from localsettings import PRELOGIN_APP_URLS
except ImportError:
    PRELOGIN_APP_URLS = [
        url(r'', include('corehq.apps.prelogin.urls')),
    ]
admin.autodiscover()

handler500 = 'corehq.apps.hqwebapp.views.server_error'
handler404 = 'corehq.apps.hqwebapp.views.not_found'
handler403 = 'corehq.apps.hqwebapp.views.no_permissions'

from corehq.apps.hqwebapp.urls import domain_specific as hqwebapp_domain_specific
from corehq.apps.settings.urls import domain_specific as settings_domain_specific
from corehq.apps.settings.urls import users_redirect, domain_redirect
from corehq.apps.sms.urls import sms_admin_interface_urls


domain_specific = [
    url(r'^logo.png', logo, name='logo'),
    url(r'^apps/', include('corehq.apps.app_manager.urls')),
    url(r'^api/', include('corehq.apps.api.urls')),
    # the receiver needs to accept posts at an endpoint that might
    # not have a slash, so don't include it at the root urlconf
    url(r'^receiver/', include('corehq.apps.receiverwrapper.urls')),
    url(r'^settings/', include(settings_domain_specific)),
    url(r'^users/', include(users_redirect)),
    url(r'^domain/', include(domain_redirect)),
    url(r'^groups/', include('corehq.apps.groups.urls')),
    url(r'^phone/', include('corehq.apps.ota.urls')),
    url(r'^phone/', include('corehq.apps.mobile_auth.urls')),
    url(r'^sms/', include('corehq.apps.sms.urls')),
    url(r'^reminders/', include('corehq.apps.reminders.urls')),
    url(r'^indicators/mvp/', include('mvp.urls')),
    url(r'^indicators/', include('corehq.apps.indicators.urls')),
    url(r'^reports/', include('corehq.apps.reports.urls')),
    url(r'^data/', include('corehq.apps.data_interfaces.urls')),
    url(r'^data_dictionary/', include('corehq.apps.data_dictionary.urls')),
    url(r'^', include(hqwebapp_domain_specific)),
    url(r'^case/', include('corehq.apps.hqcase.urls')),
    url(r'^case/', include('corehq.apps.case_search.urls')),
    url(r'^cloudcare/', include('corehq.apps.cloudcare.urls')),
    url(r'^fixtures/', include('corehq.apps.fixtures.urls')),
    url(r'^importer/', include('corehq.apps.case_importer.urls')),
    url(r'^fri/', include('custom.fri.urls')),
    url(r'^ilsgateway/', include('custom.ilsgateway.urls')),
    url(r'^ewsghana/', include('custom.ewsghana.urls')),
    url(r'^up_nrhm/', include('custom.up_nrhm.urls')),
    url(r'^', include('custom.m4change.urls')),
    url(r'^', include('custom.uth.urls')),
    url(r'^dashboard/', include('corehq.apps.dashboard.urls')),
    url(r'^configurable_reports/', include('corehq.apps.userreports.urls')),
    url(r'^performance_messaging/', include('corehq.apps.performance_sms.urls')),
    url(r'^', include('custom.icds_reports.urls')),
    url(r'^', include('custom.enikshay.urls')),
    url(r'^_base_template/$', login_and_domain_required(
        lambda request, domain: render(request, 'style/base.html', {'domain': domain})
    )),
    url(r'^zapier/', include('corehq.apps.zapier.urls')),
    url(r'^zipline/', include('custom.zipline.urls'))
]

urlpatterns = [
    url(r'^favicon\.ico$', RedirectView.as_view(
        url=static('hqwebapp/images/favicon2.png'), permanent=True)),
    url(r'^auditcare/', include('auditcare.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^analytics/', include('corehq.apps.analytics.urls')),
    url(r'^register/', include('corehq.apps.registration.urls')),
    url(r'^a/(?P<domain>%s)/' % legacy_domain_re, include(domain_specific)),
    url(r'^account/', include('corehq.apps.settings.urls')),
    url(r'^project_store(.*)$', rewrite_url),
    url(r'^exchange/', include('corehq.apps.appstore.urls')),
    url(r'^webforms/', include('touchforms.formplayer.urls')),
    url(r'', include('corehq.apps.hqwebapp.urls')),
    url(r'', include('corehq.apps.domain.urls')),
    url(r'^hq/accounting/', include('corehq.apps.accounting.urls')),
    url(r'^hq/sms/', include(sms_admin_interface_urls)),
    url(r'^hq/multimedia/', include('corehq.apps.hqmedia.urls')),
    url(r'^hq/admin/', include('corehq.apps.hqadmin.urls')),
    url(r'^hq/reports/', include(report_urls)),
    url(r'^hq/flags/', include('corehq.apps.toggle_ui.urls')),
    url(r'^hq/pillow_errors/', include('corehq.apps.hqpillow_retry.urls')),
    url(r'^hq/tour/', include('corehq.apps.tour.urls')),
    url(r'^hq/notifications/', include('corehq.apps.notifications.urls')),
    url(r'^unicel/', include('corehq.messaging.smsbackends.unicel.urls')),
    url(r'^smsgh/', include('corehq.messaging.smsbackends.smsgh.urls')),
    url(r'^push/', include('corehq.messaging.smsbackends.push.urls')),
    url(r'^apposit/', include('corehq.messaging.smsbackends.apposit.urls')),
    url(r'^tropo/', include('corehq.messaging.smsbackends.tropo.urls')),
    url(r'^twilio/', include('corehq.messaging.smsbackends.twilio.urls')),
    url(r'^dropbox/', include('corehq.apps.dropbox.urls')),
    url(r'^megamobile/', include('corehq.messaging.smsbackends.megamobile.urls')),
    url(r'^telerivet/', include('corehq.messaging.smsbackends.telerivet.urls')),
    url(r'^kookoo/', include('corehq.messaging.ivrbackends.kookoo.urls')),
    url(r'^yo/', include('corehq.messaging.smsbackends.yo.urls')),
    url(r'^gvi/', include('corehq.messaging.smsbackends.grapevine.urls')),
    url(r'^sislog/', include('corehq.messaging.smsbackends.sislog.urls')),
    url(r'^langcodes/', include('langcodes.urls')),
    url(r'^builds/', include('corehq.apps.builds.urls')),
    url(r'^downloads/temp/', include('soil.urls')),
    url(r'^test/CommCare.jar', download_test_jar, name='download_test_jar'),
    url(r'^styleguide/', include('corehq.apps.styleguide.urls')),
    url(r'^500/$', TemplateView.as_view(template_name='500.html')),
    url(r'^404/$', TemplateView.as_view(template_name='404.html')),
    url(r'^403/$', TemplateView.as_view(template_name='403.html')),
    url(r'^captcha/', include('captcha.urls')),
    url(r'^eula_basic/$', TemplateView.as_view(template_name='eula.html'), name='eula_basic'),
    url(r'^eula/$', eula, name='eula'),
    url(r'^apache_license_basic/$', TemplateView.as_view(template_name='apache_license.html'), name='apache_license_basic'),
    url(r'^apache_license/$', apache_license, name='apache_license'),
    url(r'^bsd_license_basic/$', TemplateView.as_view(template_name='bsd_license.html'), name='bsd_license_basic'),
    url(r'^bsd_license/$', bsd_license, name='bsd_license'),
    url(r'^product_agreement/$', product_agreement, name='product_agreement'),
    url(r'^exchange/cda_basic/$', TemplateView.as_view(template_name='cda.html'), name='cda_basic'),
    url(r'^exchange/cda/$', cda, name='cda'),
    url(r'^sms_in/$', sms_in, name='sms_in'),
    url(r'^unsubscribe/(?P<user_id>[\w-]+)/',
        unsubscribe, name='unsubscribe'),
    url(r'^wisepill/', include('custom.apps.wisepill.urls')),
    url(r'^pro_bono/$', ProBonoStaticView.as_view(),
        name=ProBonoStaticView.urlname),
    url(r'^ping/$', ping, name='ping'),
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    url(r'^software-plans/$', RedirectView.as_view(url=PRICING_LINK, permanent=True), name='go_to_pricing'),
    url(r'^unsubscribe_report/(?P<scheduled_report_id>[\w-]+)/'
        r'(?P<user_email>[\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4})/(?P<scheduled_report_secret>[\w-]+)/',
        ReportNotificationUnsubscribeView.as_view(), name=ReportNotificationUnsubscribeView.urlname),
] + LOCAL_APP_URLS

if settings.ENABLE_PRELOGIN_SITE:
    urlpatterns += PRELOGIN_APP_URLS

if settings.DEBUG:
    try:
        from debug_toolbar import urls as debug_toolbar_urls
        urlpatterns += [
            url(r'^__debug__/', include(debug_toolbar_urls)),
        ]
    except ImportError:
        pass

    urlpatterns += [
        url(r'^mocha/', include('corehq.apps.mocha.urls')),
    ]
