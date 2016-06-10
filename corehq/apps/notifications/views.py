from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_noop
from django.views.generic import View

from djangular.views.mixins import JSONResponseMixin, allow_remote_invocation

from dimagi.utils.decorators.memoized import memoized

from corehq import toggles
from corehq.apps.domain.decorators import login_required, require_superuser_or_developer
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.notifications.forms import NotificationCreationForm
from corehq.apps.notifications.models import Notification


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
        notifications = Notification.get_by_user(self.request.user)
        has_unread = len(filter(lambda x: not x['isRead'], notifications)) > 0
        return {
            'hasUnread': has_unread,
            'notifications': notifications,
        }

    @allow_remote_invocation
    def mark_as_read(self, in_data):
        Notification.objects.get(pk=in_data['id']).mark_as_read(self.request.user)
        return {}


class ManageNotificationView(BasePageView):
    urlname = 'manage_notifications'
    page_title = ugettext_noop("Manage Notification")
    template_name = 'notifications/manage_notifications.html'

    @method_decorator(require_superuser_or_developer)
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
                'activated': unicode(alert.activated),
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
