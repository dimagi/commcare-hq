from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from django.conf.urls import url, include
from django.shortcuts import render
from django.views.generic import TemplateView, RedirectView

from corehq.apps.app_manager.views.formdesigner import ping
from corehq.apps.appstore.views import rewrite_url
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.utils import legacy_domain_re

from django.contrib import admin
from corehq.apps.app_manager.views.phone import list_apps
from corehq.apps.domain.views.settings import logo
from corehq.apps.domain.views.pro_bono import ProBonoStaticView
from corehq.apps.hqwebapp.views import apache_license, bsd_license, cda, redirect_to_dimagi
from corehq.apps.reports.views import ReportNotificationUnsubscribeView
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.reports.urls import report_urls
from corehq.apps.registration.tasks import PRICING_LINK
from corehq.apps.hqwebapp.urls import legacy_prelogin

try:
    from localsettings import LOCAL_APP_URLS
except ImportError:
    LOCAL_APP_URLS = []

admin.autodiscover()

handler500 = 'corehq.apps.hqwebapp.views.server_error'
handler404 = 'corehq.apps.hqwebapp.views.not_found'
handler403 = 'corehq.apps.hqwebapp.views.no_permissions'

from corehq.apps.accounting.urls import domain_specific as accounting_domain_specific
from corehq.apps.hqwebapp.urls import domain_specific as hqwebapp_domain_specific
from corehq.apps.settings.urls import domain_specific as settings_domain_specific
from corehq.apps.settings.urls import users_redirect, domain_redirect
from corehq.apps.sms.urls import sms_admin_interface_urls


domain_specific = [
    url(r'^logo.png', logo, name='logo'),
    url(r'^apps/', include('corehq.apps.app_manager.urls')),
    url(r'^api/', include('corehq.apps.api.urls')),
    url(r'^receiver/', include('corehq.apps.receiverwrapper.urls')),
    url(r'^settings/', include(settings_domain_specific)),
    url(r'^enterprise/', include(accounting_domain_specific)),
    url(r'^users/', include(users_redirect)),
    url(r'^domain/', include(domain_redirect)),
    url(r'^groups/', include('corehq.apps.groups.urls')),
    url(r'^phone/', include('corehq.apps.ota.urls')),
    url(r'^phone/', include('corehq.apps.mobile_auth.urls')),
    url(r'^sms/', include('corehq.apps.sms.urls')),
    url(r'^reminders/', include('corehq.apps.reminders.urls')),
    url(r'^reports/', include('corehq.apps.reports.urls')),
    url(r'^messaging/', include('corehq.messaging.scheduling.urls')),
    url(r'^data/', include('corehq.apps.data_interfaces.urls')),
    url(r'^data_dictionary/', include('corehq.apps.data_dictionary.urls')),
    url(r'^', include(hqwebapp_domain_specific)),
    url(r'^case/', include('corehq.apps.hqcase.urls')),
    url(r'^case/', include('corehq.apps.case_search.urls')),
    url(r'^case_migrations/', include('corehq.apps.case_migrations.urls')),
    url(r'^case_templates/', include('corehq.apps.case_templates.urls')),
    url(r'^cloudcare/', include('corehq.apps.cloudcare.urls')),
    url(r'^fixtures/', include('corehq.apps.fixtures.urls')),
    url(r'^importer/', include('corehq.apps.case_importer.urls')),
    url(r'^ilsgateway/', include('custom.ilsgateway.urls')),
    url(r'^ewsghana/', include('custom.ewsghana.urls')),
    url(r'^up_nrhm/', include('custom.up_nrhm.urls')),
    url(r'^', include('custom.m4change.urls')),
    url(r'^dashboard/', include('corehq.apps.dashboard.urls')),
    url(r'^configurable_reports/', include('corehq.apps.userreports.urls')),
    url(r'^', include('custom.icds_reports.urls')),
    url(r'^', include('custom.icds.urls')),
    url(r'^', include('custom.aaa.urls')),
    url(r'^champ_cameroon/', include('custom.champ.urls')),
    url(r'^motech/', include('corehq.motech.urls')),
    url(r'^dhis2/', include('corehq.motech.dhis2.urls')),
    url(r'^openmrs/', include('corehq.motech.openmrs.urls')),
    url(r'^_base_template/$', login_and_domain_required(
        lambda request, domain: render(request, 'hqwebapp/base.html', {'domain': domain})
    )),
    url(r'^zapier/', include('corehq.apps.zapier.urls')),
    url(r'^zipline/', include('custom.zipline.urls')),
    url(r'^remote_link/', include('corehq.apps.linked_domain.urls')),
    url(r'^translations/', include('corehq.apps.translations.urls')),
]

urlpatterns = [
    url(r'^favicon\.ico$', RedirectView.as_view(
        url=static('hqwebapp/images/favicon2.png'), permanent=True)),
    url(r'^auditcare/', include('auditcare.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^analytics/', include('corehq.apps.analytics.urls')),
    url(r'^register/', include('corehq.apps.registration.urls')),
    url(r'^a/(?P<domain>%s)/' % legacy_domain_re, include(domain_specific)),
    url(r'^account/', include('corehq.apps.settings.urls')),
    url(r'^project_store(.*)$', rewrite_url),
    url(r'^exchange/', include('corehq.apps.appstore.urls')),
    url(r'', include('corehq.apps.hqwebapp.urls')),
    url(r'', include('corehq.apps.domain.urls')),
    url(r'^hq/accounting/', include('corehq.apps.accounting.urls')),
    url(r'^hq/sms/', include(sms_admin_interface_urls)),
    url(r'^hq/multimedia/', include('corehq.apps.hqmedia.urls')),
    url(r'^hq/admin/', include('corehq.apps.hqadmin.urls')),
    url(r'^hq/reports/', include(report_urls)),
    url(r'^hq/flags/', include('corehq.apps.toggle_ui.urls')),
    url(r'^hq/pillow_errors/', include('corehq.apps.hqpillow_retry.urls')),
    url(r'^hq/notifications/', include('corehq.apps.notifications.urls')),
    url(r'^unicel/', include('corehq.messaging.smsbackends.unicel.urls')),
    url(r'^smsgh/', include('corehq.messaging.smsbackends.smsgh.urls')),
    url(r'^push/', include('corehq.messaging.smsbackends.push.urls')),
    url(r'^starfish/', include('corehq.messaging.smsbackends.starfish.urls')),
    url(r'^apposit/', include('corehq.messaging.smsbackends.apposit.urls')),
    url(r'^tropo/', include('corehq.messaging.smsbackends.tropo.urls')),
    url(r'^twilio/', include('corehq.messaging.smsbackends.twilio.urls')),
    url(r'^dropbox/', include('corehq.apps.dropbox.urls')),
    url(r'^start_enterprise/', include('corehq.messaging.smsbackends.start_enterprise.urls')),
    url(r'^telerivet/', include('corehq.messaging.smsbackends.telerivet.urls')),
    url(r'^kookoo/', include('corehq.messaging.ivrbackends.kookoo.urls')),
    url(r'^yo/', include('corehq.messaging.smsbackends.yo.urls')),
    url(r'^gvi/', include('corehq.messaging.smsbackends.grapevine.urls')),
    url(r'^sislog/', include('corehq.messaging.smsbackends.sislog.urls')),
    url(r'^langcodes/', include('langcodes.urls')),
    url(r'^builds/', include('corehq.apps.builds.urls')),
    url(r'^downloads/temp/', include('soil.urls')),
    url(r'^styleguide/', include('corehq.apps.styleguide.urls')),
    url(r'^500/$', TemplateView.as_view(template_name='500.html')),
    url(r'^404/$', TemplateView.as_view(template_name='404.html')),
    url(r'^403/$', TemplateView.as_view(template_name='403.html')),
    url(r'^captcha/', include('captcha.urls')),
    url(r'^eula/$', redirect_to_dimagi('terms/')),
    url(r'^product_agreement/$', redirect_to_dimagi('terms/')),
    url(r'^apache_license_basic/$', TemplateView.as_view(template_name='apache_license.html'), name='apache_license_basic'),
    url(r'^apache_license/$', apache_license, name='apache_license'),
    url(r'^bsd_license_basic/$', TemplateView.as_view(template_name='bsd_license.html'), name='bsd_license_basic'),
    url(r'^bsd_license/$', bsd_license, name='bsd_license'),
    url(r'^exchange/cda_basic/$', TemplateView.as_view(template_name='cda.html'), name='cda_basic'),
    url(r'^exchange/cda/$', cda, name='cda'),
    url(r'^wisepill/', include('custom.apps.wisepill.urls')),
    url(r'^pro_bono/$', ProBonoStaticView.as_view(), name=ProBonoStaticView.urlname),
    url(r'^ping/$', ping, name='ping'),
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    url(r'^software-plans/$', RedirectView.as_view(url=PRICING_LINK, permanent=True), name='go_to_pricing'),
    url(r'^unsubscribe_report/(?P<scheduled_report_id>[\w-]+)/'
        r'(?P<user_email>[\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/(?P<scheduled_report_secret>[\w-]+)/',
        ReportNotificationUnsubscribeView.as_view(), name=ReportNotificationUnsubscribeView.urlname),
    url(r'^phone/list_apps', list_apps, name="list_accessible_apps")
] + LOCAL_APP_URLS

if settings.ENABLE_PRELOGIN_SITE:
    # handle redirects from old prelogin
    urlpatterns += [
        url(r'', include(legacy_prelogin)),
    ]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns += [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ]
    except ImportError:
        pass

    urlpatterns += [
        url(r'^mocha/', include('corehq.apps.mocha.urls')),
    ]
