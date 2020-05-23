import uuid

from django.db import models

from dimagi.ext.couchdbkit import DateTimeProperty, Document, StringProperty
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin

from .utils import generate_aes_key


class MobileAuthKeyRecord(SyncCouchToSQLMixin, Document):
    """

    Data model for generating the XML for mobile auth
    (from https://github.com/dimagi/commcare/wiki/CentralAuthAPI)

    """

    domain = StringProperty()
    user_id = StringProperty()

    valid = DateTimeProperty()  # initialized with 30 days before the date created
    expires = DateTimeProperty()  # just bumped up by multiple of 30 days when expired
    type = StringProperty(choices=['AES256'], default='AES256')
    key = StringProperty()

    def __init__(self, *args, **kwargs):
        super(MobileAuthKeyRecord, self).__init__(*args, **kwargs)
        if not self.key:
            self.key = generate_aes_key().decode('utf-8')
        if not self._id:
            self._id = uuid.uuid4().hex

    @property
    def uuid(self):
        return self.get_id

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLMobileAuthKeyRecord

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "user_id", "valid", "expires", "type", "key"]


def _default_uuid():
    return uuid.uuid4().hex


def _default_key():
    return generate_aes_key().decode('utf-8')


class SQLMobileAuthKeyRecord(SyncSQLToCouchMixin, models.Model):
    id = models.UUIDField(primary_key=True, default=_default_uuid)
    domain = models.CharField(max_length=126, null=False, db_index=True)
    user_id = models.CharField(max_length=255, null=False, db_index=True)

    valid = models.DateTimeField(null=False)    # initialized with 30 days before the date created
    expires = models.DateTimeField(null=False)  # just bumped up by multiple of 30 days when expired
    type = models.CharField(null=False, max_length=32, choices=[('AES256', 'AES256')], default='AES256')
    key = models.CharField(null=False, max_length=127, default=_default_key)

    class Meta:
        db_table = "mobile_auth_mobileauthkeyrecord"

    _migration_couch_id_name = "id"

    @property
    def uuid(self):
        return self.id

    @classmethod
    def _migration_get_couch_model_class(cls):
        return MobileAuthKeyRecord

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "user_id", "valid", "expires", "type", "key"]

    @classmethod
    def key_for_time(cls, domain, user_id, now):
        return cls.objects.filter(domain=domain, user_id=user_id, valid__lte=now).order_by('-valid').first()
