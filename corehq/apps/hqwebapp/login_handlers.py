from datetime import datetime
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from corehq.apps.hqwebapp.models import UserAccessLog

from dimagi.utils.web import get_ip


@receiver(user_login_failed)
def handle_failed_login(sender, credentials, request, token_failure=False, **kwargs):
    handle_access_event(UserAccessLog.TYPE_FAILURE, request, credentials['username'])


@receiver(user_logged_in)
def handle_login(sender, request, user, **kwargs):
    handle_access_event(UserAccessLog.TYPE_LOGIN, request, user.username)


@receiver(user_logged_out)
def handle_logout(sender, request, user, **kwargs):
    handle_access_event(UserAccessLog.TYPE_LOGOUT, request, user.username)


def handle_access_event(event_type, request, user_id):
    ip_address = get_ip(request)
    timestamp = datetime.now()
    agent = request.META.get('HTTP_USER_AGENT', '<unknown>')
    path = request.path
    UserAccessLog.objects.create(action=event_type, user_id=user_id, ip=ip_address,
        user_agent=agent, path=path, timestamp=timestamp)
