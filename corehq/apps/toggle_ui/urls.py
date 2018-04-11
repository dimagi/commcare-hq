from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url

from corehq.apps.toggle_ui.views import ToggleListView, ToggleEditView, toggle_app_manager_v2

urlpatterns = [
    url(r'^$', ToggleListView.as_view(), name=ToggleListView.urlname),
    url(r'^edit/(?P<toggle>[\w_-]+)/$', ToggleEditView.as_view(), name=ToggleEditView.urlname),
    url(r'^toggle_app_manager_v2/$', toggle_app_manager_v2, name="toggle_app_manager_v2"),
]
