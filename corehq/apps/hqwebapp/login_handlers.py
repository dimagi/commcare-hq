from datetime import datetime
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from corehq.apps.hqwebapp.models import UserAccessLog

from dimagi.utils.web import get_ip


@receiver(user_login_failed)
def handle_failed_login(sender, credentials, request, token_failure=False, **kwargs):
    _handle_access_event(UserAccessLog.TYPE_FAILURE, request, credentials['username'])


@receiver(user_logged_in)
def handle_login(sender, request, user, **kwargs):
    _handle_access_event(UserAccessLog.TYPE_LOGIN, request, user.username)


@receiver(user_logged_out)
def handle_logout(sender, request, user, **kwargs):
    # User can be None when the user is not authorized.
    # See: https://docs.djangoproject.com/en/3.1/ref/contrib/auth/#django.contrib.auth.signals.user_logged_out
    user_id = user.username if user else ''
    _handle_access_event(UserAccessLog.TYPE_LOGOUT, request, user_id)


def _handle_access_event(event_type, request, user_id):
    ip_address = ''
    agent = None
    path = ''

    if request:
        ip_address = get_ip(request)
        agent = request.META.get('HTTP_USER_AGENT', agent)
        path = request.path

    timestamp = datetime.now()
    UserAccessLog.objects.create(action=event_type, user_id=user_id, ip=ip_address,
        user_agent=agent, path=path, timestamp=timestamp)
