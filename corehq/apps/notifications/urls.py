from django.conf.urls import patterns, url
from corehq.apps.notifications.views import NotificationsServiceRMIView

urlpatterns = patterns(
    'corehq.apps.notifications.views',
    url(r"^service/$",
        NotificationsServiceRMIView.as_view(),
        name=NotificationsServiceRMIView.urlname),
)
