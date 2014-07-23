from datetime import datetime, timedelta
import json

from couchdbkit.ext.django.schema import *
from couchdbkit.exceptions import ResourceNotFound
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


def simple_post_with_cached_timeout(data, url, expiry=60 * 60, *args, **kwargs):
    # no control characters (e.g. '/') in keys
    key = hashlib.md5(
        '{0} timeout {1}'.format(__name__, url)
    ).hexdigest()

    cache_value = cache.get(key)

    if cache_value == 'timeout':
        raise socket.timeout('recently timed out, not retrying')
    elif cache_value == 'error':
        raise socket.timeout('recently errored, not retrying')

    try:
        resp = simple_post(data, url, *args, **kwargs)
    except socket.timeout:
        cache.set(key, 'timeout', expiry)
        raise

    if not 200 <= resp.status < 300:
        cache.set(key, 'error', expiry)
    return resp


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
            # In this case the wrap function delegates to the
            # appropriate sub-repeater types.
            pass
        else:
            # Any repeater type can be posted to the API, and the installed apps
            # determine whether we actually know about it.
            # But if we do not know about it, then may as well return nothing now
            return []

        raw_docs = cls.view('receiverwrapper/repeaters',
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
            reduce=False,
            wrap_doc=False
        )

        return [cls.wrap(repeater_doc['doc']) for repeater_doc in raw_docs
                if repeater_doc['doc']['doc_type'].replace(DELETED, '') in repeater_types]

    @classmethod
    def wrap(cls, data):
        doc_type = data['doc_type'].replace(DELETED, '')
        if cls.__name__ == Repeater.__name__:
            if doc_type in repeater_types:
                return repeater_types[doc_type].wrap(data)
            else:
                raise ResourceNotFound('Unknown repeater type: %s', data)
        else:
            return super(Repeater, cls).wrap(data)

    def retire(self):
        if DELETED not in self['doc_type']:
            self['doc_type'] += DELETED
        if DELETED not in self['base_doc']:
            self['base_doc'] += DELETED
        self.save()

    def get_headers(self, repeat_record):
        # to be overridden
        return {}

@register_repeater_type
class FormRepeater(Repeater):
    """
    Record that forms should be repeated to a new url

    """
    @memoized
    def _payload_doc(self, repeat_record):
        return XFormInstance.get(repeat_record.payload_id)

    def get_payload(self, repeat_record):
        return self._payload_doc(repeat_record).get_xml()

    def get_headers(self, repeat_record):
        return {
            "received-on": self._payload_doc(repeat_record).received_on.isoformat()+"Z"
        }

    def __unicode__(self):
        return "forwarding forms to: %s" % self.url

@register_repeater_type
class CaseRepeater(Repeater):
    """
    Record that cases should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)

    @memoized
    def _payload_doc(self, repeat_record):
        return CommCareCase.get(repeat_record.payload_id)

    def get_payload(self, repeat_record):
        return self._payload_doc(repeat_record).to_xml(version=self.version or V2)

    def get_headers(self, repeat_record):
        return {
            "server-modified-on": self._payload_doc(repeat_record).server_modified_on.isoformat()+"Z"
        }

    def __unicode__(self):
        return "forwarding cases to: %s" % self.url

@register_repeater_type
class ShortFormRepeater(Repeater):
    """
    Record that form id & case ids should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)

    @memoized
    def _payload_doc(self, repeat_record):
        return XFormInstance.get(repeat_record.payload_id)

    def get_payload(self, repeat_record):
        form = self._payload_doc(repeat_record)
        cases = CommCareCase.get_by_xform_id(form.get_id)
        return json.dumps({'form_id': form._id,
                           'received_on': json_format_datetime(form.received_on),
                           'case_ids': [case._id for case in cases]})

    def get_headers(self, repeat_record):
        return {
            "received-on": self._payload_doc(repeat_record).received_on.isoformat()+"Z"
        }

    def __unicode__(self):
        return "forwarding short form to: %s" % self.url


@register_repeater_type
class AppStructureRepeater(Repeater):
    def get_payload(self, repeat_record):
        # This is the id of the application, currently all we forward
        return repeat_record.payload_id


class RepeatRecord(Document, LockableMixIn):
    """
    An record of a particular instance of something that needs to be forwarded
    with a link to the proper repeater object
    """

    repeater_id = StringProperty()
    repeater_type = StringProperty()
    domain = StringProperty()

    last_checked = DateTimeProperty(exact=True)
    next_check = DateTimeProperty(exact=True)
    succeeded = BooleanProperty(default=False)

    payload_id = StringProperty()

    @classmethod
    def wrap(cls, data):
        for attr in ('last_checked', 'next_check'):
            value = data.get(attr)
            if not value:
                continue
            try:
                dt = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
                data[attr] = dt.isoformat() + '.000000Z'
                print data[attr]
            except ValueError:
                pass
        return super(RepeatRecord, cls).wrap(data)

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

    @classmethod
    def count(cls, domain=None):
        results = RepeatRecord.view("receiverwrapper/repeat_records_by_next_check",
            startkey=[domain],
            endkey=[domain, {}],
            reduce=True,
        ).one()
        return results['value'] if results else 0

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
        headers = self.repeater.get_headers(self)
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
