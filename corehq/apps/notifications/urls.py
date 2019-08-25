from django.conf.urls import url
from corehq.apps.notifications.views import NotificationsServiceRMIView, ManageNotificationView

urlpatterns = [
    url(r"^service/$",
        NotificationsServiceRMIView.as_view(),
        name=NotificationsServiceRMIView.urlname),
    url(r"^manage/$",
        ManageNotificationView.as_view(),
        name=ManageNotificationView.urlname),
]
