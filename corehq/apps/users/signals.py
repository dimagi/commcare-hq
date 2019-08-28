from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.contrib.auth.signals import user_logged_in
from corehq.elastic import send_to_elasticsearch


commcare_user_post_save = Signal(providing_args=["couch_user"])
couch_user_post_save = Signal(providing_args=["couch_user"])


@receiver(user_logged_in)
def set_language(sender, **kwargs):
    """
    Whenever a user logs in, attempt to set their browser session
    to the right language.
    HT: http://mirobetm.blogspot.com/2012/02/django-language-set-in-database-field.html
    """
    from corehq.apps.users.models import CouchUser
    user = kwargs['user']
    couch_user = CouchUser.from_django_user(user)
    if couch_user and couch_user.language:
        kwargs['request'].session['django_language'] = couch_user.language


# Signal that syncs django_user => couch_user
def django_user_post_save_signal(sender, instance, created, raw=False, **kwargs):
    from corehq.apps.users.models import CouchUser
    if raw:
        return
    return CouchUser.django_user_post_save_signal(sender, instance, created)


def update_user_in_es(sender, couch_user, **kwargs):
    """
    Automatically sync the user to elastic directly on save or delete
    """
    from corehq.pillows.user import transform_user_for_elasticsearch
    send_to_elasticsearch("users", transform_user_for_elasticsearch(couch_user.to_json()),
                          delete=couch_user.to_be_deleted())


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
