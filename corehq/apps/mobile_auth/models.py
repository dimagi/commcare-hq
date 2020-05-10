import uuid

from django.db import models

from dimagi.ext.couchdbkit import DateTimeProperty, Document, StringProperty

from .utils import generate_aes_key


def _default_uuid():
    return uuid.uuid4().hex


def _default_key():
    return generate_aes_key().decode('utf-8')


class MobileAuthKeyRecord(models.Model):
    """

    Data model for generating the XML for mobile auth
    (from https://github.com/dimagi/commcare/wiki/CentralAuthAPI)

    """
    uuid = models.UUIDField(primary_key=True, db_index=True, default=_default_uuid)
    domain = models.CharField(max_length=126, null=False, db_index=True)
    user_id = models.CharField(max_length=255, null=False, db_index=True)

    valid = models.DateTimeField(null=False)    # initialized with 30 days before the date created
    expires = models.DateTimeField(null=False)  # just bumped up by multiple of 30 days when expired
    type = models.CharField(null=False, max_length=32, choices=[('AES256', 'AES256')], default='AES256')
    key = models.CharField(null=False, max_length=127, default=_default_key)

    @classmethod
    def key_for_time(cls, domain, user_id, now):
        return cls.objects.filter(domain=domain, user_id=user_id, valid__lte=now).order_by('-valid').first()
