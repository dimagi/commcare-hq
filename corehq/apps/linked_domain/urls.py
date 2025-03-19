from django.urls import re_path as url

from corehq.apps.linked_domain.views import (
    DomainLinkRMIView,
    app_by_version,
    auto_update_rules,
    brief_apps,
    case_search_config,
    custom_data_models,
    data_dictionary,
    fixture,
    linkable_ucr,
    ucr_config,
    get_latest_released_app_source,
    released_app_versions,
    toggles_and_previews,
    user_roles,
    dialer_settings,
    otp_settings,
    hmac_callout_settings,
    tableau_server_and_visualizations,
)

app_name = 'linked_domain'


urlpatterns = [
    url(r'^brief_apps/$', brief_apps, name='brief_apps'),
    url(r'^app_by_version/(?P<app_id>[\w-]+)/(?P<version>\d+)/$', app_by_version, name='app_by_version'),
    url(r'^auto_update_rules/$', auto_update_rules, name='auto_update_rules'),
    url(r'^case_search_config/$', case_search_config, name='case_search_config'),
    url(r'^custom_data_models/$', custom_data_models, name='custom_data_models'),
    url(r'^data_dictionary/$', data_dictionary, name='data_dictionary'),
    url(r'^fixture/(?P<tag>[\w_-]+)$', fixture, name='fixture'),
    url(r'^ucr_config/(?P<config_id>[\w-]+)/$', ucr_config, name='ucr_config'),
    url(r'^linkable_ucr/$', linkable_ucr, name='linkable_ucr'),
    url(r'^toggles/$', toggles_and_previews, name='toggles'),
    url(r'^released_app_versions/$', released_app_versions, name='released_app_versions'),
    url(r'^release_source/(?P<app_id>[\w-]+)/$', get_latest_released_app_source,
        name='latest_released_app_source'),
    url(r'^service/$', DomainLinkRMIView.as_view(), name=DomainLinkRMIView.urlname),
    url(r'^user_roles/$', user_roles, name='user_roles'),
    url(r'^dialer_settings/$', dialer_settings, name='dialer_settings'),
    url(r'^otp_settings/$', otp_settings, name='otp_settings'),
    url(r'^hmac_callout_settings/$', hmac_callout_settings, name='hmac_callout_settings'),
    url(r'^tableau_server_and_visualizatons/$', tableau_server_and_visualizations,
        name='tableau_server_and_visualizations'),
]
