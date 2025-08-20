from django.urls import re_path as url

from corehq.apps.domain.utils import legacy_domain_re
from corehq.apps.toggle_ui.views import (
    ToggleEditView,
    ToggleListView,
    export_toggles,
    get_dimagi_users,
    set_toggle,
)

urlpatterns = [
    url(r'^$', ToggleListView.as_view(), name=ToggleListView.urlname),
    url(r'^export_toggles/$', export_toggles, name='export_toggles'),
    url(r'^get_dimagi_users/(?P<domain>%s)/$' % legacy_domain_re, get_dimagi_users, name='get_dimagi_users'),
    url(r'^edit/(?P<toggle>[\w_-]+)/$', ToggleEditView.as_view(), name=ToggleEditView.urlname),
    url(r'^set_toggle/(?P<toggle_slug>[\w_-]+)/$', set_toggle, name='set_toggle'),
]
