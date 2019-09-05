from datetime import date

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from corehq.apps.users.models import CouchUser


def clear_login_attempts(user):
    if user and user.login_attempts > 0:
        user.login_attempts = 0
        user.save()


@receiver(user_logged_in)
def clear_failed_logins_and_unlock_account(sender, request, user, **kwargs):
    couch_user = getattr(request, 'couch_user', None)
    if not couch_user:
        couch_user = CouchUser.from_django_user(user)
    clear_login_attempts(couch_user)


@receiver(user_login_failed)
def add_failed_attempt(sender, credentials, **kwargs):
    user = CouchUser.get_by_username(credentials['username'])
    if user and not user.is_locked_out() and user.supports_lockout():
        if user.attempt_date == date.today():
            user.login_attempts += 1
        else:
            user.login_attempts = 1
            user.attempt_date = date.today()
        user.save()
