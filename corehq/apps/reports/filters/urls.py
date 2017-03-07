from django.conf.urls import url

from .api import (
    EmwfOptionsView, LocationRestrictedEmwfOptions, CaseListFilterOptions, DeviceLogUsers, DeviceLogIds
)
from .location import LocationGroupFilterOptions

urlpatterns = [
   url(r'^emwf_options/$', EmwfOptionsView.as_view(), name='emwf_options'),
   url(r'^new_emwf_options/$', LocationRestrictedEmwfOptions.as_view(), name='new_emwf_options'),
   url(r'^case_list_options/$', CaseListFilterOptions.as_view(),
       name='case_list_options'
       ),
   url(r'^grouplocationfilter_options/$', LocationGroupFilterOptions.as_view(),
       name='grouplocationfilter_options'
       ),
   url(r'^device_log_users/$', DeviceLogUsers.as_view(), name='device_log_users'),
   url(r'^device_log_ids/$', DeviceLogIds.as_view(), name='device_log_ids'),
]
