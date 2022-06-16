from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import Signal

from corehq.elastic import send_to_elasticsearch

commcare_user_post_save = Signal()  # providing args: couch_user
couch_user_post_save = Signal()  # providing args: couch_user


# Signal that syncs django_user => couch_user
def django_user_post_save_signal(sender, instance, created, raw=False, **kwargs):
    from corehq.apps.users.models import CouchUser
    if raw:
        return
    return CouchUser.django_user_post_save_signal(sender, instance, created)


def _should_sync_to_es():
    # this method is useful to disable update_user_in_es in all tests
    #   but still enable it when necessary via mock
    return not settings.UNIT_TESTING


def update_user_in_es(sender, couch_user, **kwargs):
    """
    Automatically sync the user to elastic directly on save or delete
    """
    from corehq.pillows.user import transform_user_for_elasticsearch
    send_to_elasticsearch(
        "users",
        transform_user_for_elasticsearch(couch_user.to_json()),
        delete=couch_user.to_be_deleted()
    )


def apply_correct_demo_mode(sender, couch_user, **kwargs):
    from .tasks import apply_correct_demo_mode_to_loadtest_user
    apply_correct_demo_mode_to_loadtest_user.delay(couch_user.get_id)


def sync_user_phone_numbers(sender, couch_user, **kwargs):
    from corehq.apps.sms.tasks import sync_user_phone_numbers as sms_sync_user_phone_numbers
    sms_sync_user_phone_numbers.delay(couch_user.get_id)


# This gets called by UsersAppConfig when the module is set up
def connect_user_signals():
    from django.contrib.auth.models import User
    post_save.connect(django_user_post_save_signal, User,
                      dispatch_uid="django_user_post_save_signal")
    couch_user_post_save.connect(update_user_in_es, dispatch_uid="update_user_in_es")
    couch_user_post_save.connect(sync_user_phone_numbers, dispatch_uid="sync_user_phone_numbers")
    commcare_user_post_save.connect(apply_correct_demo_mode,
                                    dispatch_uid='apply_correct_demo_mode')
