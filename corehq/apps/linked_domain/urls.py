from django.conf.urls import url

from corehq.apps.linked_domain.views import (
    DomainLinkRMIView,
    app_by_version,
    brief_apps,
    case_search_config,
    custom_data_models,
    ucr_config,
    get_latest_released_app_source,
    released_app_versions,
    toggles_and_previews,
    user_roles,
)

app_name = 'linked_domain'


urlpatterns = [
    url(r'^brief_apps/$', brief_apps, name='brief_apps'),
    url(r'^app_by_version/(?P<app_id>[\w-]+)/(?P<version>\d+)/$', app_by_version, name='app_by_version'),
    url(r'^case_search_config/$', case_search_config, name='case_search_config'),
    url(r'^custom_data_models/$', custom_data_models, name='custom_data_models'),
    url(r'^ucr_config/(?P<config_id>[\w-]+)/$', ucr_config, name='ucr_config'),
    url(r'^toggles/$', toggles_and_previews, name='toggles'),
    url(r'^released_app_versions/$', released_app_versions, name='released_app_versions'),
    url(r'^release_source/(?P<app_id>[\w-]+)/$', get_latest_released_app_source,
        name='latest_released_app_source'),
    url(r'^service/$', DomainLinkRMIView.as_view(), name=DomainLinkRMIView.urlname),
    url(r'^user_roles/$', user_roles, name='user_roles'),
]
