from datetime import datetime
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from corehq.apps.domain.decorators import login_or_digest_ex
from corehq.apps.mobile_auth.utils import new_key_record, get_mobile_auth_payload
from corehq.apps.mobile_auth.models import MobileAuthKeyRecord
from dimagi.utils.parsing import string_to_datetime

class FetchKeyRecords(object):
    def __init__(self, domain, user_id, last_issued):
        self.domain = domain
        self.user_id = user_id
        self.last_issued = last_issued
        self.now = datetime.utcnow()

    def key_for_time(self, now):
        return MobileAuthKeyRecord.current_for_user(
            domain=self.domain,
            user_id=self.user_id,
            now=now,
        )

    def get_or_create_current_record(self):
        key_record = self.key_for_time(self.now)
        if not key_record:
            key_record = new_key_record(self.domain, self.user_id, self.now)
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
        return filter(None, [old_key, current_key])


    def get_payload(self):
        return get_mobile_auth_payload(
            key_records=self.get_key_records(),
            domain=self.domain,
            now=self.now,
        )

@login_or_digest_ex(allow_cc_users=True)
@require_GET
def fetch_key_records(request, domain):
    last_issued = request.GET.get('last_issued')
    if last_issued:
        last_issued = string_to_datetime(last_issued).replace(tzinfo=None)
    user_id = request.couch_user.user_id
    payload = FetchKeyRecords(domain, user_id, last_issued).get_payload()
    return HttpResponse(payload)