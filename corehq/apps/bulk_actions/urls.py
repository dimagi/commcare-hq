from django.conf.urls import url

from corehq.apps.bulk_actions.views import EditBulkActionView, ListBulkActionsView


urlpatterns = [
    url(r'^list/$', ListBulkActionsView.as_view(), name=ListBulkActionsView.urlname),
    url(r'^edit/$', EditBulkActionView.as_view(), name=EditBulkActionView.urlname),
]
