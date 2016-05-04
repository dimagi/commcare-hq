from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import View
from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation
from corehq import toggles
from corehq.apps.domain.decorators import login_required
from corehq.apps.notifications.models import Notification
from corehq.apps.notifications.util import get_notifications_by_user


class NotificationsServiceRMIView(JSONResponseMixin, View):
    urlname = "notifications_service"

    @method_decorator(login_required)
    @method_decorator(toggles.NOTIFICATIONS.required_decorator())
    def dispatch(self, request, *args, **kwargs):
        return super(NotificationsServiceRMIView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return HttpResponse("foo")

    @allow_remote_invocation
    def get_notifications(self, in_data):
        # todo always grab alerts if they are still relevant
        notifications = get_notifications_by_user(self.request.user)
        has_unread = len(filter(lambda x: x['isRead'], notifications)) > 0
        return {
            'hasUnread': has_unread,
            'notifications': notifications,
        }

    @allow_remote_invocation
    def mark_as_read(self, in_data):
        Notification.objects.get(pk=in_data['id']).users_read.add(self.request.user)
        return {}
