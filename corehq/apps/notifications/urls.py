from django.urls import re_path as url

from corehq.apps.notifications.views import (
    ManageNotificationView,
    NotificationsServiceRMIView,
)

urlpatterns = [
    url(r"^service/$",
        NotificationsServiceRMIView.as_view(),
        name=NotificationsServiceRMIView.urlname),
    url(r"^manage/$",
        ManageNotificationView.as_view(),
        name=ManageNotificationView.urlname),
]
