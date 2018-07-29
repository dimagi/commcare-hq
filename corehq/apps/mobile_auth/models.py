from __future__ import absolute_import

from __future__ import unicode_literals
import uuid

from dimagi.ext.couchdbkit import Document, StringProperty, DateTimeProperty
from dimagi.utils.parsing import json_format_datetime
from .utils import generate_aes_key


class MobileAuthKeyRecord(Document):
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
            self.key = generate_aes_key()
        if not self._id:
            self._id = uuid.uuid4().hex

    @property
    def uuid(self):
        return self.get_id

    @classmethod
    def key_for_time(cls, domain, user_id, now):
        now_json = json_format_datetime(now)
        key_record = cls.view('mobile_auth/key_records',
            startkey=[domain, user_id, now_json],
            endkey=[domain, user_id, ""],
            descending=True,
            limit=1,
            include_docs=True,
        ).first()
        return key_record
