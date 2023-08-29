from django.conf.urls import re_path as url

from .api import (
    CaseListFilterOptions,
    DeviceLogIds,
    DeviceLogUsers,
    EmwfOptionsView,
    MobileWorkersOptionsView,
    CaseListActionOptions,
    EnterpriseUserOptions,
)
from .location import LocationGroupFilterOptions

urlpatterns = [
    url(r'^emwf_options_all_users/$', EmwfOptionsView.as_view(), name='emwf_options_all_users'),
    url(r'^users_options/$', MobileWorkersOptionsView.as_view(), name=MobileWorkersOptionsView.urlname),
    url(r'^enterprise_users_options/$', EnterpriseUserOptions.as_view(), name="enterprise_user_options"),
    url(r'^case_list_options/$', CaseListFilterOptions.as_view(), name='case_list_options'),
    url(r'^case_action_options/$', CaseListActionOptions.as_view(), name='case_action_options'),
    url(r'^grouplocationfilter_options/$', LocationGroupFilterOptions.as_view(),
        name='grouplocationfilter_options'),
    url(r'^device_log_users/$', DeviceLogUsers.as_view(), name='device_log_users'),
    url(r'^device_log_ids/$', DeviceLogIds.as_view(), name='device_log_ids'),
]
