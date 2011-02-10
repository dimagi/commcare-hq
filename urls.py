from django.conf.urls.defaults import *
from django.conf import settings
import os
from corehq.apps.domain.urls import domain_re

from corehq.util.modules import try_import

# Uncomment the next two lines to enable the admin:
from django.contrib import admin

admin.autodiscover()


from corehq.apps.hqwebapp.urls import domain_specific as hqwebapp_domain_specific
domain_specific = patterns('',
    (r'^apps/', include('corehq.apps.app_manager.urls')),
    (r'^receiver', include('corehq.apps.receiver.urls')),
    (r'^migration', include('corehq.apps.migration.urls')),
    (r'^users/', include('corehq.apps.users.urls')),
    (r'^groups/', include('corehq.apps.groups.urls')),
    (r'^phone/', include('corehq.apps.phone.urls')),
    (r'^sms/', include('corehq.apps.sms.urls')),
    (r'^reports/', include('corehq.apps.reports.urls')),
    # include only those urls in hqwebapp which are domain-specific
    (r'^', include(hqwebapp_domain_specific)),
    (r'^', include('django_user_registration.urls')),
    (r'^help/', include('corehq.apps.help.urls')),
)

urlpatterns = patterns('',
    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^a/(?P<domain>%s)/' % domain_re, include(domain_specific)),
    (r'^couch/', include('djangocouch.urls')),
    (r'^couchlog/', include('couchlog.urls')),
    (r'^xep/', include('xep_hq_server.urls')),
    (r'', include('corehq.apps.hqwebapp.urls')),
    (r'', include('corehq.apps.domain.urls')),
)


#django-staticfiles static/ url mapper
if settings.DEBUG:
    urlpatterns += patterns('staticfiles.views',
        url(r'^static/(?P<path>.*)$', 'serve'),
    )


