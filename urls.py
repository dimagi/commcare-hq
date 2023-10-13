from django.conf import settings
from django.conf.urls import include, re_path as url
from django.contrib import admin
from django.shortcuts import render
from django.views.generic import RedirectView, TemplateView

from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.extensions import extension_points
from corehq.apps.enterprise.urls import \
    domain_specific as enterprise_domain_specific
from corehq.apps.api.urls import user_urlpatterns as user_api_urlpatterns
from corehq.apps.app_manager.views.formdesigner import ping
from corehq.apps.app_manager.views.phone import list_apps
from corehq.apps.domain.decorators import login_and_domain_required
from corehq.apps.domain.utils import legacy_domain_re
from corehq.apps.domain.views.base import covid19
from corehq.apps.domain.views.feedback import submit_feedback
from corehq.apps.domain.views.pro_bono import ProBonoStaticView
from corehq.apps.domain.views.settings import logo
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import static
from corehq.apps.hqwebapp.urls import \
    domain_specific as hqwebapp_domain_specific
from corehq.apps.hqwebapp.urls import legacy_prelogin
from corehq.apps.hqwebapp.views import (
    apache_license,
    bsd_license,
    no_permissions,
    not_found,
    redirect_to_dimagi,
    server_error,
)
from corehq.apps.registration.tasks import PRICING_LINK
from corehq.apps.reports.views import ReportNotificationUnsubscribeView
from corehq.apps.settings.urls import domain_redirect
from corehq.apps.settings.urls import \
    domain_specific as settings_domain_specific
from corehq.apps.settings.urls import users_redirect
from corehq.apps.sms.urls import sms_admin_interface_urls

try:
    from localsettings import LOCAL_APP_URLS
except ImportError:
    LOCAL_APP_URLS = []

admin.autodiscover()

handler500 = server_error
handler404 = not_found
handler403 = no_permissions


domain_specific = [
    url(r'^logo.png', logo, name='logo'),
    url(r'^apps/', include('corehq.apps.app_manager.urls')),
    url(r'^api/', include('corehq.apps.api.urls')),
    url(r'^receiver/', include('corehq.apps.receiverwrapper.urls')),
    url(r'^settings/', include(settings_domain_specific)),
    url(r'^enterprise/', include(enterprise_domain_specific)),
    url(r'^users/', include(users_redirect)),
    url(r'^domain/', include(domain_redirect)),
    url(r'^groups/', include('corehq.apps.groups.urls')),
    url(r'^phone/', include('corehq.apps.ota.urls')),
    url(r'^phone/', include('corehq.apps.mobile_auth.urls')),
    url(r'^sms/', include('corehq.apps.sms.urls')),
    url(r'^email/', include('corehq.apps.email.urls')),
    url(r'^reminders/', include('corehq.apps.reminders.urls')),
    url(r'^reports/', include('corehq.apps.reports.urls')),
    url(r'^messaging/', include('corehq.messaging.scheduling.urls')),
    url(r'^data/', include('corehq.apps.data_interfaces.urls')),
    url(r'^data_dictionary/', include('corehq.apps.data_dictionary.urls')),
    url(r'^', include(hqwebapp_domain_specific)),
    url(r'^case/', include('corehq.apps.hqcase.urls')),
    url(r'^case/', include('corehq.apps.case_search.urls')),
    url(r'^cloudcare/', include('corehq.apps.cloudcare.urls')),
    url(r'^geospatial/', include('corehq.apps.geospatial.urls')),
    url(r'^fixtures/', include('corehq.apps.fixtures.urls')),
    url(r'^importer/', include('corehq.apps.case_importer.urls')),
    url(r'^up_nrhm/', include('custom.up_nrhm.urls')),
    url(r'^dashboard/', include('corehq.apps.dashboard.urls')),
    url(r'^configurable_reports/', include('corehq.apps.userreports.urls')),
    url(r'^champ_cameroon/', include('custom.champ.urls')),
    url(r'^motech/', include('corehq.motech.urls')),
    url(r'^dhis2/', include('corehq.motech.dhis2.urls')),
    url(r'^', include('corehq.motech.fhir.urls')),
    url(r'^openmrs/', include('corehq.motech.openmrs.urls')),
    url(r'^_base_template/$', login_and_domain_required(
        lambda request, domain: render(request, 'hqwebapp/bootstrap3/base_navigation.html', {'domain': domain})
    )),
    url(r'^zapier/', include('corehq.apps.zapier.urls')),
    url(r'^remote_link/', include('corehq.apps.linked_domain.urls')),
    url(r'^translations/', include('corehq.apps.translations.urls')),
    url(r'^submit_feedback/$', submit_feedback, name='submit_feedback'),
    url(r'^integration/', include('corehq.apps.integration.urls')),
    url(r'^registries/', include('corehq.apps.registry.urls')),
]

for url_module in extension_points.domain_specific_urls():
    domain_specific.append(url(r'^', include(url_module)))


urlpatterns = [
    url(r'^favicon\.ico$', RedirectView.as_view(
        url=static('hqwebapp/images/favicon2.png'), permanent=True)),
    url(r'^auditcare/', include('corehq.apps.auditcare.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^analytics/', include('corehq.apps.analytics.urls')),
    url(r'^api/', include(user_api_urlpatterns)),
    url(r'^register/', include('corehq.apps.registration.urls')),
    url(r'^a/(?P<domain>%s)/' % legacy_domain_re, include(domain_specific)),
    url(r'^account/', include('corehq.apps.settings.urls')),
    url(r'^sso/(?P<idp_slug>[\w-]+)/', include('corehq.apps.sso.urls')),
    url(r'', include('corehq.apps.hqwebapp.urls')),
    url(r'', include('corehq.apps.domain.urls')),
    url(r'^hq/accounting/', include('corehq.apps.accounting.urls')),
    url(r'^hq/sms/', include(sms_admin_interface_urls)),
    url(r'^hq/multimedia/', include('corehq.apps.hqmedia.urls')),
    url(r'^hq/admin/', include('corehq.apps.hqadmin.urls')),
    url(r'^hq/admin/', include('corehq.util.metrics.urls')),
    url(r'^hq/flags/', include('corehq.apps.toggle_ui.urls')),
    url(r'^hq/notifications/', include('corehq.apps.notifications.urls')),
    url(r'^unicel/', include('corehq.messaging.smsbackends.unicel.urls')),
    url(r'^smsgh/', include('corehq.messaging.smsbackends.smsgh.urls')),
    url(r'^push/', include('corehq.messaging.smsbackends.push.urls')),
    url(r'^starfish/', include('corehq.messaging.smsbackends.starfish.urls')),
    url(r'^trumpia/', include('corehq.messaging.smsbackends.trumpia.urls')),
    url(r'^apposit/', include('corehq.messaging.smsbackends.apposit.urls')),
    url(r'^tropo/', include('corehq.messaging.smsbackends.tropo.urls')),
    url(r'^turn/', include('corehq.messaging.smsbackends.turn.urls')),
    url(r'^twilio/', include('corehq.messaging.smsbackends.twilio.urls')),
    url(r'^infobip/', include('corehq.messaging.smsbackends.infobip.urls')),
    url(r'^pinpoint/', include('corehq.messaging.smsbackends.amazon_pinpoint.urls')),
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
    url(r'^500/$', use_bootstrap5(TemplateView.as_view(template_name='500.html'))),
    url(r'^404/$', use_bootstrap5(TemplateView.as_view(template_name='404.html'))),
    url(r'^403/$', use_bootstrap5(TemplateView.as_view(template_name='403.html'))),
    url(r'^eula/$', redirect_to_dimagi('terms/')),
    url(r'^product_agreement/$', redirect_to_dimagi('terms/')),
    url(r'^apache_license_basic/$',
        TemplateView.as_view(template_name='apache_license.html'),
        name='apache_license_basic'),
    url(r'^apache_license/$', apache_license, name='apache_license'),
    url(r'^bsd_license_basic/$', TemplateView.as_view(template_name='bsd_license.html'), name='bsd_license_basic'),
    url(r'^bsd_license/$', bsd_license, name='bsd_license'),
    url(r'^covid19/$', covid19, name='covid19'),
    url(r'^pro_bono/$', ProBonoStaticView.as_view(), name=ProBonoStaticView.urlname),
    url(r'^ping/$', ping, name='ping'),
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    url(r'^software-plans/$', RedirectView.as_view(url=PRICING_LINK, permanent=True), name='go_to_pricing'),
    url(r'^unsubscribe_report/(?P<scheduled_report_id>[\w-]+)/'
        r'(?P<user_email>[\w.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/(?P<scheduled_report_secret>[\w-]+)/',
        ReportNotificationUnsubscribeView.as_view(), name=ReportNotificationUnsubscribeView.urlname),
    url(r'^phone/list_apps', list_apps, name="list_accessible_apps"),
    url(r'^oauth/', include('corehq.apps.oauth_integrations.urls')),
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
