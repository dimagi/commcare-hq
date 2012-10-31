from django.conf.urls.defaults import *
from corehq.apps.domain.urls import domain_settings
from corehq.apps.cloudcare.urls import settings_urls as cloudcare_settings

domain_specific = patterns('',
    url(r'^$', 'corehq.apps.settings.views.default', name="settings_default"),
    (r'^users/', include('corehq.apps.users.urls')),
    (r'^project/', include(domain_settings)),
    (r'^cloudcare/', include(cloudcare_settings)),
    url(r'^api/id_mapping/$', 'corehq.apps.settings.views.project_id_mapping', name="project_id_mapping")

)

users_redirect = patterns('corehq.apps.settings.views',
    (r'^$', 'redirect_users'),
    (r'^(?P<old_url>[\w_\\\/\-]+)/$', 'redirect_users'))

domain_redirect = patterns('corehq.apps.settings.views',
    (r'^$', 'redirect_domain_settings'),
    (r'^(?P<old_url>[\w_\\\/\-]+)/$', 'redirect_domain_settings'))