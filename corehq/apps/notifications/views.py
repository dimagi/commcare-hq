from __future__ import absolute_import
from __future__ import unicode_literals
from django.urls import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from django.views.generic import View

from djng.views.mixins import JSONResponseMixin, allow_remote_invocation, JSONResponseException

from memoized import memoized

from corehq.apps.domain.decorators import login_required, require_superuser
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.notifications.forms import NotificationCreationForm
from corehq.apps.notifications.models import Notification, LastSeenNotification, \
    IllegalModelStateException, DismissedUINotify
import six


class NotificationsServiceRMIView(JSONResponseMixin, View):
    urlname = "notifications_service"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(NotificationsServiceRMIView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return HttpResponse("foo")

    @allow_remote_invocation
    def get_notifications(self, in_data):
        # todo always grab alerts if they are still relevant
        notifications = Notification.get_by_user(self.request.user, self.request.couch_user)
        has_unread = len([x for x in notifications if not x['isRead']]) > 0
        last_seen_notification_date = LastSeenNotification.get_last_seen_notification_date_for_user(
            self.request.user
        )
        return {
            'hasUnread': has_unread,
            'notifications': notifications,
            'lastSeenNotificationDate': last_seen_notification_date
        }

    @allow_remote_invocation
    def mark_as_read(self, in_data):
        Notification.objects.get(pk=in_data['id']).mark_as_read(self.request.user)
        return {}

    @allow_remote_invocation
    def save_last_seen(self, in_data):
        if 'notification_id' not in in_data:
            raise JSONResponseException('notification_id is required')
        notification = get_object_or_404(Notification, pk=in_data['notification_id'])
        try:
            notification.set_as_last_seen(self.request.user)
        except IllegalModelStateException as e:
            raise JSONResponseException(six.text_type(e))
        return {
            'activated': notification.activated
        }

    @allow_remote_invocation
    def dismiss_ui_notify(self, in_data):
        if 'slug' not in in_data:
            raise JSONResponseException('slug for ui notify is required')
        DismissedUINotify.dismiss_notification(self.request.user, in_data['slug'])
        return {
            'dismissed': DismissedUINotify.is_notification_dismissed(self.request.user, in_data['slug'])
        }


class ManageNotificationView(BasePageView):
    urlname = 'manage_notifications'
    page_title = ugettext_noop("Manage Notification")
    template_name = 'notifications/manage_notifications.html'

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(ManageNotificationView, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def create_form(self):
        if self.request.method == 'POST' and 'submit' in self.request.POST:
            return NotificationCreationForm(self.request.POST)
        return NotificationCreationForm()

    @property
    def page_context(self):
        return {
            'alerts': [{
                'content': alert.content,
                'url': alert.url,
                'type': alert.get_type_display(),
                'activated': six.text_type(alert.activated),
                'isActive': alert.is_active,
                'id': alert.id,
            } for alert in Notification.objects.order_by('-created').all()],
            'form': self.create_form,
        }

    @property
    def page_url(self):
        return reverse(self.urlname)

    def post(self, request, *args, **kwargs):
        if 'submit' in request.POST and self.create_form.is_valid():
            self.create_form.save()
        elif 'activate' in request.POST:
            note = Notification.objects.filter(pk=request.POST.get('alert_id')).first()
            note.activate()
        elif 'deactivate' in request.POST:
            note = Notification.objects.filter(pk=request.POST.get('alert_id')).first()
            note.deactivate()
        elif 'remove' in request.POST:
            Notification.objects.filter(pk=request.POST.get('alert_id')).delete()
        return self.get(request, *args, **kwargs)
