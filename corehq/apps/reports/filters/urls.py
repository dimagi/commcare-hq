from django.conf.urls import *

from .api import EmwfOptionsView
from .case_list import CaseListFilterOptions

urlpatterns = patterns('',
    url(r'^emwf_options/$', EmwfOptionsView.as_view(), name='emwf_options'),
    url(r'^case_list_options/$', CaseListFilterOptions.as_view(),
        name='case_list_options'
    ),
)
