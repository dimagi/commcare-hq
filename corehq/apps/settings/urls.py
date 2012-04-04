from django.conf.urls.defaults import *
from corehq.apps.domain.urls import domain_specific as domain_domain_specific

domain_specific = patterns('',
    url(r'^$', 'corehq.apps.settings.views.default', name="settings_default"),
    (r'^users/', include('corehq.apps.users.urls')),
    (r'^project/', include(domain_domain_specific)),
)

users_redirect = patterns('corehq.apps.settings.views',
    (r'^$', 'redirect_users'),
    (r'^(?P<old_url>[\w_\\\/\-]+)/$', 'redirect_users'))

domain_redirect = patterns('corehq.apps.settings.views',
    (r'^$', 'redirect_domain_settings'),
    (r'^(?P<old_url>[\w_\\\/\-]+)/$', 'redirect_domain_settings'))