import re

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_noop
from django.views.generic import View

from memoized import memoized

from corehq.apps.accounting.models import Subscription, SoftwarePlanEdition, SubscriptionType
from corehq.apps.domain.decorators import login_required, require_superuser
from corehq.apps.groups.models import Group
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.notifications.forms import NotificationCreationForm
from corehq.apps.notifications.models import (
    DismissedUINotify,
    IllegalModelStateException,
    LastSeenNotification,
    Notification,
)
from corehq.util.jqueryrmi import (
    JSONResponseException,
    JSONResponseMixin,
    allow_remote_invocation,
)


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
        subscribed_plan = Subscription.get_subscribed_plan_by_domain(self.get_domain())
        pro_tier_editions = [SoftwarePlanEdition.PRO, SoftwarePlanEdition.ADVANCED, SoftwarePlanEdition.ENTERPRISE]
        if subscribed_plan.plan.edition in pro_tier_editions:
            plan_tier = 'pro'
        else:
            plan_tier = 'basic'

        notifications = Notification.get_by_user(self.request.user,
                                                 self.request.couch_user,
                                                 plan_tier=plan_tier,
                                                 hide_features=self._should_hide_feature_notifs(
                                                     self.get_domain(), plan_tier))
        has_unread = len([x for x in notifications if not x['isRead']]) > 0
        last_seen_notification_date = LastSeenNotification.get_last_seen_notification_date_for_user(
            self.request.user
        )
        return {
            'hasUnread': has_unread,
            'notifications': notifications,
            'lastSeenNotificationDate': last_seen_notification_date
        }

    @staticmethod
    def _should_hide_feature_notifs(domain, plan):
        if plan == 'pro' and Group.get_case_sharing_groups(domain, wrap=False):
            return True
        sub = Subscription.get_active_subscription_by_domain(domain)
        return sub is not None and sub.service_type in [
            SubscriptionType.IMPLEMENTATION,
            SubscriptionType.SANDBOX,
        ]

    @allow_remote_invocation
    def mark_as_read(self, in_data):
        Notification.objects.get(pk=in_data['id']).mark_as_read(self.request.user)
        return {
            'email': self.request.couch_user.username,
            'domain': self.get_domain()
        }

    @allow_remote_invocation
    def save_last_seen(self, in_data):
        if 'notification_id' not in in_data:
            raise JSONResponseException('notification_id is required')
        notification = get_object_or_404(Notification, pk=in_data['notification_id'])
        try:
            notification.set_as_last_seen(self.request.user)
        except IllegalModelStateException as e:
            raise JSONResponseException(str(e))
        return {
            'activated': notification.activated,
            'email': self.request.couch_user.username,
            'domain': self.get_domain()
        }

    def get_domain(self):
        domain_match_regex = r'(?<=/a/)([^\s/]{1,25}?)(?=\s*/)'
        domain = re.search(domain_match_regex, self.request.META['HTTP_REFERER'])
        if domain:
            return domain.group(0)
        return self.request.couch_user.domains[0]

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
    page_title = gettext_noop("Manage Notification")
    template_name = 'notifications/manage_notifications.html'

    @method_decorator(require_superuser)
    @method_decorator(use_bootstrap5)
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
                'activated': str(alert.activated),
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
