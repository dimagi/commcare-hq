from datetime import datetime, timedelta
import json

from couchdbkit.ext.django.schema import *
from django.core.cache import cache
import socket
import hashlib

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2, LEGAL_VERSIONS

from couchforms.models import XFormInstance
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.post import simple_post
from dimagi.utils.couch import LockableMixIn


repeater_types = {}


def register_repeater_type(cls):
    repeater_types[cls.__name__] = cls
    return cls


def simple_post_with_cached_timeout(data, url, expiry=60*60, *args, **kwargs):
    # no control characters (e.g. '/') in keys
    key = hashlib.md5(
        '{0} timeout {1}'.format(__name__, url)
    ).hexdigest()

    if cache.get(key) == 'timeout':
        raise socket.timeout('recently timed out, not retrying')
    try:
        return simple_post(data, url, *args, **kwargs)
    except socket.timeout:
        cache.set(key, 'timeout', expiry)
        raise


DELETED = "-Deleted"


class Repeater(Document, UnicodeMixIn):
    base_doc = 'Repeater'

    domain = StringProperty()
    url = StringProperty()

    def register(self, payload, next_check=None):
        try:
            payload_id = payload.get_id
        except Exception:
            payload_id = payload
        repeat_record = RepeatRecord(
            repeater_id=self.get_id,
            repeater_type=self.doc_type,
            domain=self.domain,
            next_check=next_check or datetime.utcnow(),
            payload_id=payload_id
        )
        repeat_record.save()
        return repeat_record

    @classmethod
    def by_domain(cls, domain):
        key = [domain]
        if repeater_types.has_key(cls.__name__):
            key.append(cls.__name__)
        elif cls.__name__ == Repeater.__name__:
            pass
        else:
            raise Exception("Unknown Repeater type: %s" % cls.__name__)

        return cls.view('receiverwrapper/repeaters',
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
            reduce=False
        )

    @classmethod
    def wrap(cls, data):
        doc_type = data['doc_type'].replace(DELETED, '')
        if cls.__name__ == Repeater.__name__:
            return repeater_types.get(doc_type, cls).wrap(data)
        else:
            return super(Repeater, cls).wrap(data)

    def retire(self):
        if DELETED not in self['doc_type']:
            self['doc_type'] += DELETED
        if DELETED not in self['base_doc']:
            self['base_doc'] += DELETED
        self.save()

@register_repeater_type
class FormRepeater(Repeater):
    """
    Record that forms should be repeated to a new url

    """

    def get_payload(self, repeat_record):
        return XFormInstance.get(repeat_record.payload_id).get_xml()

    def __unicode__(self):
        return "forwarding forms to: %s" % self.url

@register_repeater_type
class CaseRepeater(Repeater):
    """
    Record that cases should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)

    def get_payload(self, repeat_record):
        return CommCareCase.get(repeat_record.payload_id).to_xml(version=self.version)

    def __unicode__(self):
        return "forwarding cases to: %s" % self.url

@register_repeater_type
class ShortFormRepeater(Repeater):
    """
    Record that form id & case ids should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)

    def get_payload(self, repeat_record):
        form = XFormInstance.get(repeat_record.payload_id)
        cases = CommCareCase.get_by_xform_id(form.get_id)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})

    def __unicode__(self):
        return "forwarding short form to: %s" % self.url

class RepeatRecord(Document, LockableMixIn):
    """
    An record of a particular instance of something that needs to be forwarded
    with a link to the proper repeater object
    """

    repeater_id = StringProperty()
    repeater_type = StringProperty()
    domain = StringProperty()

    last_checked = DateTimeProperty()
    next_check = DateTimeProperty()
    succeeded = BooleanProperty(default=False)

    payload_id = StringProperty()

    @property
    @memoized
    def repeater(self):
        return Repeater.get(self.repeater_id)

    @property
    def url(self):
        return self.repeater.url

    @classmethod
    def all(cls, domain=None, due_before=None, limit=None):
        json_now = json_format_datetime(due_before or datetime.utcnow())
        repeat_records = RepeatRecord.view("receiverwrapper/repeat_records_by_next_check",
            startkey=[domain],
            endkey=[domain, json_now, {}],
            include_docs=True,
            reduce=False,
            limit=limit,
        )
        return repeat_records

    def update_success(self):
        self.last_checked = datetime.utcnow()
        self.next_check = None
        self.succeeded = True
    
    def update_failure(self):
        # we use an exponential back-off to avoid submitting to bad urls
        # too frequently.
        assert(self.succeeded == False)
        assert(self.next_check is not None)
        now = datetime.utcnow()
        window = timedelta(minutes=0)
        if self.last_checked:
            window = self.next_check - self.last_checked
            window += (window // 2) # window *= 1.5
        if window < timedelta(minutes=60):
            window = timedelta(minutes=60)

        self.last_checked = now
        self.next_check = self.last_checked + window

    def try_now(self):
        # try when we haven't succeeded and either we've
        # never checked, or it's time to check again
        return not self.succeeded

    def get_payload(self):
        return self.repeater.get_payload(self)

    def fire(self, max_tries=3, post_fn=None):
        payload = self.get_payload()
        post_fn = post_fn or simple_post_with_cached_timeout
        headers = None
        if self.repeater_type == "FormRepeater":
            form = XFormInstance.get(self.payload_id)
            headers = {
                "received-on": form.received_on.isoformat()+"Z",
            }
        if self.try_now():
            # we don't use celery's version of retry because
            # we want to override the success/fail each try
            for i in range(max_tries):
                try:
                    resp = post_fn(payload, self.url, headers=headers)
                    if 200 <= resp.status < 300:
                        self.update_success()
                        break
                except Exception, e:
                    pass # some other connection issue probably
            if not self.succeeded:
                # mark it failed for later and give up
                self.update_failure()

# import signals
from corehq.apps.receiverwrapper import signals
