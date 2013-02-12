from __future__ import absolute_import
from datetime import datetime
from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty
from dimagi.utils.parsing import json_format_datetime
from .utils import generate_aes_key

class MobileAuthKeyRecord(Document):
    """

    Data model for generating the XML for mobile auth
    (from https://bitbucket.org/commcare/commcare/wiki/CentralAuthAPI)

    """

    domain = StringProperty()
    user_id = StringProperty()

    valid = DateTimeProperty()
    expires = DateTimeProperty()
    type = StringProperty(choices=['AES256'], default='AES256')
    key = StringProperty()

    def __init__(self, *args, **kwargs):
        super(MobileAuthKeyRecord, self).__init__(*args, **kwargs)
        if not self.key:
            self.key = generate_aes_key()
        if not self._id:
            self._id = self.get_db().server.next_uuid()

    @property
    def uuid(self):
        return self.get_id

    @classmethod
    def current_for_user(cls, domain, user_id, now=None):
        now = now or datetime.utcnow()
        now_json = json_format_datetime(now)
        key_record = cls.view('mobile_auth/key_records',
            startkey=[domain, user_id, now_json],
            descending=True,
            limit=1,
            include_docs=True,
            stale='update_after',
        ).first()
        if key_record and now < key_record.expires:
            return key_record
        else:
            return None
