from django.urls import re_path as url

from corehq.apps.toggle_ui.views import (
    ToggleEditView,
    ToggleListView,
    set_toggle,
    export_toggles,
)

urlpatterns = [
    url(r'^$', ToggleListView.as_view(), name=ToggleListView.urlname),
    url(r'^export_toggles/$', export_toggles, name='export_toggles'),
    url(r'^edit/(?P<toggle>[\w_-]+)/$', ToggleEditView.as_view(), name=ToggleEditView.urlname),
    url(r'^set_toggle/(?P<toggle_slug>[\w_-]+)/$', set_toggle, name='set_toggle'),
]
