from datetime import date

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from corehq.apps.users.models import CouchUser

@receiver(user_logged_in)
def clear_failed_logins_and_unlock_account(sender, request, user, **kwargs):
    user = CouchUser.from_django_user(user)
    if user.is_web_user():
        user.login_attempts = 0
        user.save()

@receiver(user_login_failed)
def add_failed_attempt(sender, credentials, **kwargs):
    user = CouchUser.get_by_username(credentials['username'])
    if user and user.is_web_user():
        if user.login_attempts > 4:
            return
        if user.attempt_date == date.today():
            user.login_attempts += 1
        else:
            user.login_attempts = 1
            user.attempt_date = date.today()
        user.save()
