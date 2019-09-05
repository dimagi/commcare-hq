import base64
import os
from datetime import datetime, timedelta

from django.utils.translation import ugettext as _

from corehq.apps.mobile_auth.xml import AuthKeys, KeyRecord, OpenRosaResponse


def generate_aes_key():
    # get 32 byte key
    bin_key = os.urandom(32)
    return base64.b64encode(bin_key)


def new_key_record(domain, user_id, now=None, valid=None):
    """
    return initialized but unsaved MobileAuthKeyRecord

    """
    from corehq.apps.mobile_auth.models import MobileAuthKeyRecord
    now = now or datetime.utcnow()
    valid = valid or now
    record = MobileAuthKeyRecord(
        domain=domain,
        user_id=user_id,
        valid=valid,
    )
    bump_expiry(record, now=now)

    return record


def bump_expiry(record, now=None):
    """
    initialize or extend expiry to after now
    in increments of a month

    """
    now = now or datetime.utcnow()
    record.expires = record.expires or now

    while record.expires <= now:
        record.expires += timedelta(days=30)


def get_mobile_auth_payload(key_records, domain, issued=None, now=None):
    """
    formats a list of key record documents in the xml format outlined in
    https://github.com/dimagi/commcare/wiki/CentralAuthAPI

    makes sure to set xml object properties in a standard order
    for ease of testing

    """
    now = now or datetime.utcnow()

    issued = issued or now

    def _OpenRosaResponse():
        x = OpenRosaResponse()
        x.auth_keys = _auth_keys()
        x.message = _('Here are your keys!')
        return x

    def _auth_keys():
        x = AuthKeys(
            key_records=list(_key_record())
        )
        x.domain = domain
        x.issued = issued
        return x

    def _key_record():
        for key_record in key_records:
            x = KeyRecord()
            for attr in ['valid', 'expires', 'uuid', 'type', 'key']:
                setattr(x, attr, getattr(key_record, attr))

            yield x

    return _OpenRosaResponse().serializeDocument(pretty=True)
