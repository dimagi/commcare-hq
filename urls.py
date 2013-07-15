from django.conf.urls.defaults import *
from django.conf import settings
from corehq.apps.domain.utils import legacy_domain_re

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
from corehq.apps.orgs.urls import organizations_urls
from corehq.apps.reports.urls import report_urls

try:
    from localsettings import LOCAL_APP_URLS
except ImportError:
    LOCAL_APP_URLS = ()
admin.autodiscover()

handler500 = 'corehq.apps.hqwebapp.views.server_error'
handler404 = 'corehq.apps.hqwebapp.views.not_found'

from corehq.apps.hqwebapp.urls import domain_specific as hqwebapp_domain_specific
from corehq.apps.settings.urls import domain_specific as settings_domain_specific
from corehq.apps.settings.urls import users_redirect, domain_redirect
from corehq.apps.adm.urls import adm_admin_interface_urls
from corehq.apps.sms.urls import sms_admin_interface_urls


domain_specific = patterns('',
    (r'^apps/', include('corehq.apps.app_manager.urls')),
    (r'^api/', include('corehq.apps.api.urls')),
    # the receiver needs to accept posts at an endpoint that might
    # not have a slash, so don't include it at the root urlconf
    (r'^receiver', include('corehq.apps.receiverwrapper.urls')),
    (r'^migration/', include('corehq.apps.migration.urls')),
    (r'^settings/', include(settings_domain_specific)),
    (r'^users/', include(users_redirect)),
    (r'^domain/', include(domain_redirect)),
    (r'^groups/', include('corehq.apps.groups.urls')),
    (r'^phone/', include('corehq.apps.ota.urls')),
    (r'^phone/', include('corehq.apps.mobile_auth.urls')),
    (r'^sms/', include('corehq.apps.sms.urls')),
    (r'^commtrack/', include('corehq.apps.commtrack.urls')),
    (r'^reminders/', include('corehq.apps.reminders.urls')),
    (r'^indicators/mvp/', include('mvp.urls')),
    (r'^indicators/', include('corehq.apps.indicators.urls')),
    (r'^reports/adm/', include('corehq.apps.adm.urls')),
    (r'^reports/', include('corehq.apps.reports.urls')),
    (r'^data/', include('corehq.apps.data_interfaces.urls')),
    (r'^', include(hqwebapp_domain_specific)),
    (r'^case/', include('corehq.apps.hqcase.urls')),
    (r'^submitlist/', include('corehq.apps.hqsofabed.urls')),
    (r'^cleanup/', include('corehq.apps.cleanup.urls')),
    (r'^phonelog/', include('phonelog.urls')),
    (r'^cloudcare/', include('corehq.apps.cloudcare.urls')),
    (r'^fixtures/', include('corehq.apps.fixtures.urls')),
    (r'^importer/', include('corehq.apps.importer.urls')),
    (r'^sqlextract/', include('ctable_view.urls')),
)

urlpatterns = patterns('',
    # Uncomment the next line to enable the admin:
    (r'^auditcare/', include('auditcare.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'^register/', include('corehq.apps.registration.urls')),
    (r'^a/(?P<domain>%s)/' % legacy_domain_re, include(domain_specific)),
    (r'^o/', include('corehq.apps.orgs.urls')),
    (r'^organizations/', include(organizations_urls)),
    (r'^account/', include('corehq.apps.settings.urls')),
    (r'^couch/', include('djangocouch.urls')),
    (r'^project_store(.*)$', 'corehq.apps.appstore.views.rewrite_url'),
    (r'^exchange/', include('corehq.apps.appstore.urls')),
    (r'^webforms/', include('touchforms.formplayer.urls')),
    (r'', include('corehq.apps.hqwebapp.urls')),
    (r'', include('corehq.apps.domain.urls')),
    (r'^adm/', include(adm_admin_interface_urls)),
    (r'^announcements/', include('corehq.apps.announcements.urls')),
    (r'^hq/sms/', include(sms_admin_interface_urls)),
    (r'^hq/billing/', include('hqbilling.urls')),
    (r'^hq/multimedia/', include('corehq.apps.hqmedia.urls')),
    (r'^hq/admin/', include('corehq.apps.hqadmin.urls')),
    (r'^hq/prescriptions/', include('corehq.apps.prescriptions.urls')),
    (r'^hq/reports/', include(report_urls)),
    (r'^couchlog/', include('couchlog.urls')),
    (r'^formtranslate/', include('formtranslate.urls')),
    (r'^unicel/', include('corehq.apps.unicel.urls')),
    (r'^tropo/', include('corehq.apps.tropo.urls')),
    (r'^telerivet/', include('corehq.apps.telerivet.urls')),
    (r'^kookoo/', include('corehq.apps.kookoo.urls')),
    (r'^yo/', include('corehq.apps.yo.urls')),
    (r'^sislog/', include('corehq.apps.sislog.urls')),
    (r'^langcodes/', include('langcodes.urls')),
    (r'^builds/', include('corehq.apps.builds.urls')),
    (r'^downloads/temp/', include('soil.urls')),
    (r'^test/CommCare.jar', 'corehq.apps.app_manager.views.download_test_jar'),
    (r'^translations/', include('corehq.apps.translations.urls')),
    (r'^sqlextract/', include('ctable_view.urls')),
    (r'^500/$', 'django.views.generic.simple.direct_to_template', {'template': '500.html'}),
    (r'^404/$', 'django.views.generic.simple.direct_to_template', {'template': '404.html'}),
    url(r'^eula_basic/$', 'django.views.generic.simple.direct_to_template', {'template': 'eula.html'}, name='eula_basic'),
    url(r'^eula/$', 'corehq.apps.hqwebapp.views.eula', name='eula'),
    url(r'^apache_license_basic/$', 'django.views.generic.simple.direct_to_template', {'template': 'apache_license.html'}, name='apache_license_basic'),
    url(r'^apache_license/$', 'corehq.apps.hqwebapp.views.apache_license', name='apache_license'),
    url(r'^bsd_license_basic/$', 'django.views.generic.simple.direct_to_template', {'template': 'bsd_license.html'}, name='bsd_license_basic'),
    url(r'^bsd_license/$', 'corehq.apps.hqwebapp.views.bsd_license', name='bsd_license'),
    url(r'^exchange/cda_basic/$', 'django.views.generic.simple.direct_to_template', {'template': 'cda.html'}, name='cda_basic'),
    url(r'^exchange/cda/$', 'corehq.apps.hqwebapp.views.cda', name='cda'),
    url(r'^sms_in/$', 'corehq.apps.sms.views.sms_in', name='sms_in'),
) + patterns('', *LOCAL_APP_URLS)

# django rosetta support if configured
if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        url(r'^rosetta/', include('rosetta.urls')),
    )

#django-staticfiles static/ url mapper
if settings.DEBUG:
    urlpatterns += patterns('django.contrib.staticfiles.views',
        url(r'^static/(?P<path>.*)$', 'serve'),
    )

