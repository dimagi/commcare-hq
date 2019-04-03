from __future__ import absolute_import, unicode_literals

from django.conf.urls import url

from corehq.apps.toggle_ui.views import (
    ToggleEditView,
    ToggleListView,
    set_toggle,
)

urlpatterns = [
    url(r'^$', ToggleListView.as_view(), name=ToggleListView.urlname),
    url(r'^edit/(?P<toggle>[\w_-]+)/$', ToggleEditView.as_view(), name=ToggleEditView.urlname),
    url(r'^set_toggle/(?P<toggle_slug>[\w_-]+)/$', set_toggle, name='set_toggle'),
]
