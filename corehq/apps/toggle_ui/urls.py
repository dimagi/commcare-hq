from django.conf.urls import url

from corehq.apps.toggle_ui.views import ToggleListView, ToggleEditView, enable_vellum_beta

urlpatterns = [
    url(r'^$', ToggleListView.as_view(), name=ToggleListView.urlname),
    url(r'^edit/(?P<toggle>[\w_-]+)/$', ToggleEditView.as_view(), name=ToggleEditView.urlname),
    url(r'^enable_vellum_beta/$', enable_vellum_beta, name="enable_vellum_beta"),
]
