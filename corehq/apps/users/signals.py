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


class ElasticUserUpdater:
    """Implemented as a callable instance rather than a function so that test
    code which wishes to disable this behavior can do so by patching this
    class's ``__call__`` method. This makes said test code less fragile because
    it won't depend on knowing exactly *how* the ``__call__`` method performs
    the user sync in Elasticsearch."""

    def transform(self, value):
        from corehq.pillows.user import transform_user_for_elasticsearch
        return transform_user_for_elasticsearch(value)

    def __call__(self, sender, couch_user, **kwargs):
        """Automatically sync the user to elastic directly on save or delete"""
        if couch_user.to_be_deleted():
            user_adapter.delete(couch_user.user_id)
        else:
            user_adapter.index(self.transform(couch_user.to_json()))


update_user_in_es = ElasticUserUpdater()


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
