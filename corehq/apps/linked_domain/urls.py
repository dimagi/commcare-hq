
from django.conf.urls import url

from corehq.apps.linked_domain.views import (
    toggles_and_previews,
    case_search_config,
    custom_data_models,
    user_roles,
    get_latest_released_app_source,
    DomainLinkRMIView,
)

app_name = 'linked_domain'


urlpatterns = [
    url(r'^toggles/$', toggles_and_previews, name='toggles'),
    url(r'^custom_data_models/$', custom_data_models, name='custom_data_models'),
    url(r'^user_roles/$', user_roles, name='user_roles'),
    url(r'^case_search_config/$', case_search_config, name='case_search_config'),
    url(r'^release_source/(?P<app_id>[\w-]+)/$', get_latest_released_app_source,
        name='latest_released_app_source'),
    url(r'^service/$', DomainLinkRMIView.as_view(), name=DomainLinkRMIView.urlname),
]
