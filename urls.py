from django.conf import settings
from django.conf.urls import patterns, url, include
from django.shortcuts import render
from django.views.generic import TemplateView, RedirectView

from corehq.apps.app_manager.views import download_test_jar
from corehq.apps.app_manager.views.formdesigner import ping
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
    LOCAL_APP_URLS = ()

try:
    from localsettings import PRELOGIN_APP_URLS
except ImportError:
    PRELOGIN_APP_URLS = (
        (r'', include('corehq.apps.prelogin.urls')),
    )
admin.autodiscover()

handler500 = 'corehq.apps.hqwebapp.views.server_error'
handler404 = 'corehq.apps.hqwebapp.views.not_found'
handler403 = 'corehq.apps.hqwebapp.views.no_permissions'

from corehq.apps.hqwebapp.urls import domain_specific as hqwebapp_domain_specific
from corehq.apps.settings.urls import domain_specific as settings_domain_specific
from corehq.apps.settings.urls import users_redirect, domain_redirect
from corehq.apps.sms.urls import sms_admin_interface_urls


domain_specific = patterns('',
    url(r'^logo.png', logo, name='logo'),
    (r'^apps/', include('corehq.apps.app_manager.urls')),
    (r'^api/', include('corehq.apps.api.urls')),
    # the receiver needs to accept posts at an endpoint that might
    # not have a slash, so don't include it at the root urlconf
    (r'^receiver', include('corehq.apps.receiverwrapper.urls')),
    (r'^settings/', include(settings_domain_specific)),
    (r'^users/', include(users_redirect)),
    (r'^domain/', include(domain_redirect)),
    (r'^groups/', include('corehq.apps.groups.urls')),
    (r'^phone/', include('corehq.apps.ota.urls')),
    (r'^phone/', include('corehq.apps.mobile_auth.urls')),
    (r'^sms/', include('corehq.apps.sms.urls')),
    (r'^reminders/', include('corehq.apps.reminders.urls')),
    (r'^indicators/mvp/', include('mvp.urls')),
    (r'^indicators/', include('corehq.apps.indicators.urls')),
    (r'^reports/', include('corehq.apps.reports.urls')),
    (r'^data/', include('corehq.apps.data_interfaces.urls')),
    (r'^', include(hqwebapp_domain_specific)),
    (r'^case/', include('corehq.apps.hqcase.urls')),
    (r'^case/', include('corehq.apps.case_search.urls')),
    (r'^cloudcare/', include('corehq.apps.cloudcare.urls')),
    (r'^fixtures/', include('corehq.apps.fixtures.urls')),
    (r'^importer/', include('corehq.apps.importer.urls')),
    (r'^fri/', include('custom.fri.urls')),
    (r'^ilsgateway/', include('custom.ilsgateway.urls')),
    (r'^ewsghana/', include('custom.ewsghana.urls')),
    (r'^up_nrhm/', include('custom.up_nrhm.urls')),
    (r'^', include('custom.m4change.urls')),
    (r'^', include('custom.uth.urls')),
    (r'^dashboard/', include('corehq.apps.dashboard.urls')),
    (r'^configurable_reports/', include('corehq.apps.userreports.urls')),
    (r'^performance_messaging/', include('corehq.apps.performance_sms.urls')),
    (r'^preview_app/', include('corehq.apps.preview_app.urls')),
    (r'^', include('custom.icds_reports.urls')),
    (r'^', include('custom.enikshay.urls')),
    (r'^_base_template/$', login_and_domain_required(
        lambda request, domain: render(request, 'style/base.html', {'domain': domain})
    )),
    (r'^zapier/', include('corehq.apps.zapier.urls', namespace='zapier')),
    (r'^zipline/', include('custom.zipline.urls'))
)

urlpatterns = patterns('',
    (r'^favicon\.ico$', RedirectView.as_view(
        url=static('hqwebapp/img/favicon2.png'))),
    (r'^auditcare/', include('auditcare.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'^analytics/', include('corehq.apps.analytics.urls')),
    (r'^register/', include('corehq.apps.registration.urls')),
    (r'^a/(?P<domain>%s)/' % legacy_domain_re, include(domain_specific)),
    (r'^account/', include('corehq.apps.settings.urls')),
    (r'^project_store(.*)$', 'corehq.apps.appstore.views.rewrite_url'),
    (r'^exchange/', include('corehq.apps.appstore.urls')),
    (r'^webforms/', include('touchforms.formplayer.urls')),
    (r'', include('corehq.apps.hqwebapp.urls')),
    (r'', include('corehq.apps.domain.urls')),
    (r'^hq/accounting/', include('corehq.apps.accounting.urls')),
    (r'^hq/sms/', include(sms_admin_interface_urls)),
    (r'^hq/multimedia/', include('corehq.apps.hqmedia.urls')),
    (r'^hq/admin/', include('corehq.apps.hqadmin.urls')),
    (r'^hq/reports/', include(report_urls)),
    (r'^hq/flags/', include('corehq.apps.toggle_ui.urls')),
    (r'^hq/pillow_errors/', include('corehq.apps.hqpillow_retry.urls')),
    (r'^hq/tour/', include('corehq.apps.tour.urls')),
    (r'^hq/notifications/', include('corehq.apps.notifications.urls')),
    (r'^couchlog/', include('couchlog.urls')),
    (r'^unicel/', include('corehq.messaging.smsbackends.unicel.urls')),
    (r'^smsgh/', include('corehq.messaging.smsbackends.smsgh.urls')),
    (r'^push/', include('corehq.messaging.smsbackends.push.urls')),
    (r'^apposit/', include('corehq.messaging.smsbackends.apposit.urls')),
    (r'^tropo/', include('corehq.messaging.smsbackends.tropo.urls')),
    (r'^twilio/', include('corehq.messaging.smsbackends.twilio.urls')),
    (r'^dropbox/', include('corehq.apps.dropbox.urls')),
    (r'^megamobile/', include('corehq.messaging.smsbackends.megamobile.urls')),
    (r'^telerivet/', include('corehq.messaging.smsbackends.telerivet.urls')),
    (r'^kookoo/', include('corehq.messaging.ivrbackends.kookoo.urls')),
    (r'^yo/', include('corehq.messaging.smsbackends.yo.urls')),
    (r'^gvi/', include('corehq.messaging.smsbackends.grapevine.urls')),
    (r'^sislog/', include('corehq.messaging.smsbackends.sislog.urls')),
    (r'^langcodes/', include('langcodes.urls')),
    (r'^builds/', include('corehq.apps.builds.urls')),
    (r'^downloads/temp/', include('soil.urls')),
    url(r'^test/CommCare.jar', download_test_jar, name='download_test_jar'),
    (r'^styleguide/', include('corehq.apps.styleguide.urls')),
    (r'^500/$', TemplateView.as_view(template_name='500.html')),
    (r'^404/$', TemplateView.as_view(template_name='404.html')),
    (r'^403/$', TemplateView.as_view(template_name='403.html')),
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
    (r'^wisepill/', include('custom.apps.wisepill.urls')),
    url(r'^pro_bono/$', ProBonoStaticView.as_view(),
        name=ProBonoStaticView.urlname),
    url(r'^ping/$', 'corehq.apps.app_manager.views.formdesigner.ping', name='ping'),
    url(r'^ping/$', ping, name='ping'),
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    url(r'^software-plans/$', RedirectView.as_view(url=PRICING_LINK), name='go_to_pricing'),
    url(r'^unsubscribe_report/(?P<scheduled_report_id>[\w-]+)/'
        r'(?P<user_email>[\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,4})/(?P<scheduled_report_secret>[\w-]+)/',
        ReportNotificationUnsubscribeView.as_view(), name=ReportNotificationUnsubscribeView.urlname),
) + patterns('', *LOCAL_APP_URLS)

if settings.ENABLE_PRELOGIN_SITE:
    urlpatterns += patterns('', *PRELOGIN_APP_URLS)

if settings.DEBUG:
    urlpatterns += patterns('',
        url(r'^mocha/', include('corehq.apps.mocha.urls')),
    )
