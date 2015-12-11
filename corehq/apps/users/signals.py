from __future__ import absolute_import
import logging
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.contrib.auth.signals import user_logged_in
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.elastic import send_to_elasticsearch

from couchforms.signals import successful_form_received
from casexml.apps.phone.xml import VALID_USER_REGISTRATION_XMLNSES


commcare_user_post_save = Signal(providing_args=["couch_user"])
couch_user_post_save = Signal(providing_args=["couch_user"])


@receiver(user_logged_in)
def set_language(sender, **kwargs):
    """
    Whenever a user logs in, attempt to set their browser session
    to the right language.
    HT: http://mirobetm.blogspot.com/2012/02/django-language-set-in-database-field.html
    """
    user = kwargs['user']
    couch_user = CouchUser.from_django_user(user)
    if couch_user and couch_user.language:
        kwargs['request'].session['django_language'] = couch_user.language


# Signal that syncs django_user => couch_user
def django_user_post_save_signal(sender, instance, created, **kwargs):
    return CouchUser.django_user_post_save_signal(sender, instance, created)


def update_user_in_es(sender, couch_user, **kwargs):
    """
    Automatically sync the user to elastic directly on save or delete
    """
    send_to_elasticsearch("users", couch_user.to_json(),
                          delete=couch_user.to_be_deleted())


def create_user_from_commcare_registration(sender, xform, **kwargs):
    """
    Automatically create Couch users whenever a registration xform is received

    # this comes in as xml that looks like:
    # <n0:registration xmlns:n0="openrosa.org/user-registration">
    # <username>user</username>
    # <password>pw</password>
    # <uuid>MTBZJTDO3SCT2ONXAQ88WM0CH</uuid>
    # <date>2008-01-07</date>
    # <registering_phone_id>NRPHIOUSVEA215AJL8FFKGTVR</registering_phone_id>
    # <user_data> ... some custom stuff </user_data>
    """
    if xform.xmlns not in VALID_USER_REGISTRATION_XMLNSES:
        return False

    try:
        CommCareUser.create_or_update_from_xform(xform)
    except Exception, e:
        logging.exception(e)
        raise


# This gets called by UsersAppConfig when the module is set up
def connect_user_signals():
    post_save.connect(django_user_post_save_signal, User,
                      dispatch_uid="django_user_post_save_signal")
    successful_form_received.connect(create_user_from_commcare_registration,
                                     dispatch_uid="create_user_from_commcare_registration")
    couch_user_post_save.connect(update_user_in_es, dispatch_uid="update_user_in_es")
