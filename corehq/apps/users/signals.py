from django.db.models.signals import post_save
from django.dispatch import Signal

from corehq.apps.es.users import user_adapter

commcare_user_post_save = Signal()  # providing args: couch_user
couch_user_post_save = Signal()  # providing args: couch_user


# Signal that syncs django_user => couch_user
def django_user_post_save_signal(sender, instance, created, raw=False, **kwargs):
    from corehq.apps.users.models import CouchUser
    if raw:
        return
    return CouchUser.django_user_post_save_signal(sender, instance, created)


def update_user_in_es(sender, couch_user, **kwargs):
    """Automatically sync the user to elastic directly on save or delete"""
    _update_user_in_es(couch_user)


def _update_user_in_es(couch_user):
    """Implemented as a nested function so that test code which wishes to
    disable this behavior can do so by patching this function, making said test
    code less fragile because it won't depend on knowing exactly *how* this
    function performs the sync.
    """
    if couch_user.to_be_deleted():
        user_adapter.delete(couch_user.user_id)
    else:
        user_adapter.index(couch_user)


def apply_correct_demo_mode(sender, couch_user, **kwargs):
    from .tasks import apply_correct_demo_mode_to_loadtest_user
    apply_correct_demo_mode_to_loadtest_user.delay(couch_user.get_id)


def sync_user_phone_numbers(sender, couch_user, **kwargs):
    from corehq.apps.sms.tasks import sync_user_phone_numbers as sms_sync_user_phone_numbers
    sms_sync_user_phone_numbers.delay(couch_user.get_id)


def remove_test_cases(sender, couch_user, **kwargs):
    from corehq.apps.users.tasks import remove_users_test_cases
    if not couch_user.is_web_user() and not couch_user.is_active:
        remove_users_test_cases.delay(couch_user.domain, [couch_user.user_id])


# This gets called by UsersAppConfig when the module is set up
def connect_user_signals():
    from django.contrib.auth.models import User
    post_save.connect(django_user_post_save_signal, User,
                      dispatch_uid="django_user_post_save_signal")
    couch_user_post_save.connect(update_user_in_es, dispatch_uid="update_user_in_es")
    couch_user_post_save.connect(sync_user_phone_numbers, dispatch_uid="sync_user_phone_numbers")
    commcare_user_post_save.connect(apply_correct_demo_mode,
                                    dispatch_uid='apply_correct_demo_mode')
    commcare_user_post_save.connect(remove_test_cases, dispatch_uid='remove_test_cases')
