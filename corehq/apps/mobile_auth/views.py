from __future__ import absolute_import
from __future__ import unicode_literals
import datetime

from corehq.apps.domain.auth import BASIC
from corehq.util.datadog.utils import count_by_response_code
from django.http import HttpResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import api_auth, domain_admin_required, mobile_auth
from corehq.apps.mobile_auth.utils import new_key_record, get_mobile_auth_payload, bump_expiry
from corehq.apps.mobile_auth.models import MobileAuthKeyRecord
from corehq.apps.users.util import update_device_meta
from corehq.toggles import ENIKSHAY
from corehq.apps.users.models import CommCareUser
from dimagi.utils.parsing import string_to_datetime


class FetchKeyRecords(object):

    def __init__(self, domain, user_id, last_issued):
        self.domain = domain
        self.user_id = user_id
        self.last_issued = last_issued
        self.now = datetime.datetime.utcnow()

    def key_for_time(self, now):
        return MobileAuthKeyRecord.key_for_time(
            domain=self.domain,
            user_id=self.user_id,
            now=now,
        )

    def get_or_create_current_record(self):
        key_record = self.key_for_time(self.now)
        if not key_record:
            key_record = new_key_record(
                domain=self.domain,
                user_id=self.user_id,
                now=self.now,
                valid=self.now - datetime.timedelta(days=30),
            )
            key_record.save()
        elif key_record.expires <= self.now:
            bump_expiry(key_record, now=self.now)
            key_record.save()
        return key_record

    def get_key_records(self):
        if self.last_issued:
            old_key = self.key_for_time(self.last_issued)
        else:
            old_key = None
        current_key = self.get_or_create_current_record()
        if old_key and current_key.uuid == old_key.uuid:
            current_key = None
        return [_f for _f in [old_key, current_key] if _f]

    def get_payload(self):
        return get_mobile_auth_payload(
            key_records=self.get_key_records(),
            domain=self.domain,
            now=self.now,
        )


@mobile_auth
@require_GET
@count_by_response_code('commcare.auth_keys.fetch.count')
def fetch_key_records(request, domain):
    last_issued = request.GET.get('last_issued')
    if last_issued:
        last_issued = string_to_datetime(last_issued).replace(tzinfo=None)
    user_id = request.couch_user.user_id
    payload = FetchKeyRecords(domain, user_id, last_issued).get_payload()
    update_device_meta(request.couch_user, request.GET.get('device_id'))
    return HttpResponse(payload)


@api_auth
@domain_admin_required
@require_GET
def admin_fetch_key_records(request, domain):
    last_issued = request.GET.get('last_issued')
    if last_issued:
        last_issued = string_to_datetime(last_issued).replace(tzinfo=None)
    username = request.GET.get('as', '')
    key_user = CommCareUser.get_by_username(username)
    if not key_user:
        return HttpResponseNotFound('User %s not found.' % username)
    payload = FetchKeyRecords(domain, key_user._id, last_issued).get_payload()
    return HttpResponse(payload)
