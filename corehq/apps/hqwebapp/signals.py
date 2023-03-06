from datetime import date

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from couchdbkit import ResourceConflict

from corehq.apps.users.models import CouchUser
from corehq.util.metrics import metrics_counter


def clear_login_attempts(user):
    if user and user.login_attempts > 0:
        try:
            user.login_attempts = 0
            user.save()
        except ResourceConflict:
            updated_user = CouchUser.get_by_username(user.username)
            clear_login_attempts(updated_user)


@receiver(user_logged_in)
def clear_failed_logins_and_unlock_account(sender, request, user, **kwargs):
    couch_user = getattr(request, 'couch_user', None)
    if not couch_user:
        couch_user = CouchUser.from_django_user(user)
    clear_login_attempts(couch_user)


@receiver(user_login_failed)
def add_failed_attempt(sender, credentials, token_failure=False, **kwargs):
    user = CouchUser.get_by_username(credentials['username'], strict=True)
    if not user:
        metrics_counter('commcare.auth.invalid_user')
        return

    if token_failure:
        metrics_counter('commcare.auth.invalid_token')

    locked_out = user.is_locked_out()

    if locked_out:
        lockout_result = 'locked_out'
    else:
        lockout_result = 'should_be_locked_out' if user.should_be_locked_out() else 'allowed_to_retry'

    metrics_counter('commcare.auth.failed_attempts', tags={
        'result': lockout_result
    })

    if user.attempt_date != date.today():
        user.login_attempts = 0
        user.attempt_date = date.today()

    user.login_attempts += 1

    try:
        user.save()
    except ResourceConflict:
        # swallow this exception to ensure the user still sees an auth failed
        # error, not a 500
        return
