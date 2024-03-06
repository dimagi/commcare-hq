from django.urls import include, re_path as url

from corehq.apps.cloudcare.urls import settings_urls as cloudcare_settings
from corehq.apps.commtrack.urls import settings_urls as commtrack_settings
from corehq.apps.domain.urls import domain_settings
from corehq.apps.locations.urls import settings_urls as location_settings
from corehq.apps.products.urls import settings_urls as product_settings
from corehq.apps.programs.urls import settings_urls as program_settings
from corehq.apps.settings.views import (
    ApiKeyView,
    ChangeMyPasswordView,
    DefaultMySettingsView,
    EnableMobilePrivilegesView,
    MyAccountSettingsView,
    MyProjectsList,
    default,
    project_id_mapping,
    redirect_domain_settings,
    redirect_users,
)

urlpatterns = [
    url(r'^$', DefaultMySettingsView.as_view(), name=DefaultMySettingsView.urlname),
    url(r'^settings/$', MyAccountSettingsView.as_view(), name=MyAccountSettingsView.urlname),
    url(r'^api_keys/$', ApiKeyView.as_view(), name=ApiKeyView.urlname),
    url(r'^projects/$', MyProjectsList.as_view(), name=MyProjectsList.urlname),
    url(r'^password/$', ChangeMyPasswordView.as_view(), name=ChangeMyPasswordView.urlname),
    url(r'^mobile_privileges/$', EnableMobilePrivilegesView.as_view(), name=EnableMobilePrivilegesView.urlname),
]

domain_specific = [
    url(r'^$', default, name="settings_default"),
    url(r'^users/', include('corehq.apps.users.urls')),
    url(r'^project/', include(domain_settings)),
    url(r'^cloudcare/', include(cloudcare_settings)),
    url(r'^commtrack/', include(commtrack_settings)),
    url(r'^products/', include(product_settings)),
    url(r'^programs/', include(program_settings)),
    url(r'^locations/', include(location_settings)),
    url(r'^api/id_mapping/$', project_id_mapping, name="project_id_mapping"),
    url(r'^events/', include('corehq.apps.events.urls')),
]

users_redirect = [
    url(r'^$', redirect_users, name='redirect_users'),
    url(r'^(?P<old_url>[\w_\\\/\-]+)/$', redirect_users, name='redirect_users')
]

domain_redirect = [
    url(r'^$', redirect_domain_settings, name='redirect_domain_settings'),
    url(r'^(?P<old_url>[\w_\\\/\-]+)/$', redirect_domain_settings, name='redirect_domain_settings')
]
