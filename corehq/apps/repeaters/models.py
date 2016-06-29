import base64
from collections import namedtuple
from datetime import datetime, timedelta
import logging
import urllib
import urlparse
from requests.exceptions import Timeout, ConnectionError
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.form_processor.exceptions import XFormNotFound
from corehq.util.datadog.metrics import REPEATER_ERROR_COUNT
from corehq.util.datadog.utils import log_counter
from corehq.util.quickcache import quickcache

from dimagi.ext.couchdbkit import *
from couchdbkit.exceptions import ResourceNotFound
from django.core.cache import cache
import hashlib

from casexml.apps.case.xml import V2, LEGAL_VERSIONS
from corehq.apps.receiverwrapper.exceptions import DuplicateFormatException, IgnoreDocument
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors

from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.post import simple_post

from .dbaccessors import (
    get_pending_repeat_record_count,
    get_failure_repeat_record_count,
    get_success_repeat_record_count,
)
from .const import (
    MAX_RETRY_WAIT,
    MIN_RETRY_WAIT,
    RECORD_FAILURE_STATE,
    RECORD_SUCCESS_STATE,
    RECORD_PENDING_STATE,
    POST_TIMEOUT,
)
from .exceptions import RequestConnectionError


repeater_types = {}


def register_repeater_type(cls):
    repeater_types[cls.__name__] = cls
    return cls


def simple_post_with_cached_timeout(data, url, expiry=60 * 60, force_send=False, *args, **kwargs):
    # no control characters (e.g. '/') in keys
    key = hashlib.md5(
        '{0} timeout {1}'.format(__name__, url)
    ).hexdigest()

    cache_value = cache.get(key)

    if cache_value and not force_send:
        raise RequestConnectionError(cache_value)

    try:
        resp = simple_post(data, url, *args, **kwargs)
    except (Timeout, ConnectionError), e:
        cache.set(key, e.message, expiry)
        raise RequestConnectionError(e.message)

    if not 200 <= resp.status_code < 300:
        message = u'Status Code {}: {}'.format(resp.status_code, resp.reason)
        cache.set(key, message, expiry)
        raise RequestConnectionError(message)
    return resp


DELETED = "-Deleted"

FormatInfo = namedtuple('FormatInfo', 'name label generator_class')


class GeneratorCollection(object):
    """Collection of format_name to Payload Generators for a Repeater class

    args:
        repeater_class: A valid child class of Repeater class
    """

    def __init__(self, repeater_class):
        self.repeater_class = repeater_class
        self.default_format = ''
        self.format_generator_map = {}

    def add_new_format(self, format_name, format_label, generator_class, is_default=False):
        """Adds a new format->generator mapping to the collection

        args:
            format_name: unique name to identify the format
            format_label: label to be displayed to the user
            generator_class: child class of .repeater_generators.BasePayloadGenerator

        kwargs:
            is_default: True if the format_name should be default format

        exceptions:
            raises DuplicateFormatException if format is added with is_default while other
            default exists
            raises DuplicateFormatException if format_name alread exists in the collection
        """
        if is_default and self.default_format:
            raise DuplicateFormatException("A default format already exists for this repeater.")
        elif is_default:
            self.default_format = format_name
        if format_name in self.format_generator_map:
            raise DuplicateFormatException("There is already a Generator with this format name.")

        self.format_generator_map[format_name] = FormatInfo(
            name=format_name,
            label=format_label,
            generator_class=generator_class
        )

    def get_default_format(self):
        """returns default format"""
        return self.default_format

    def get_default_generator(self):
        """returns generator class for the default format"""
        raise self.format_generator_map[self.default_format].generator_class

    def get_all_formats(self, for_domain=None):
        """returns all the formats added to this repeater collection"""
        return [(name, format.label) for name, format in self.format_generator_map.iteritems()
                if not for_domain or format.generator_class.enabled_for_domain(for_domain)]

    def get_generator_by_format(self, format):
        """returns generator class given a format"""
        return self.format_generator_map[format].generator_class


class RegisterGenerator(object):
    """Decorator to register new formats and Payload generators for Repeaters

    args:
        repeater_cls: A child class of Repeater for which the new format is being added
        format_name: unique identifier for the format
        format_label: description for the format

    kwargs:
        is_default: whether the format is default to the repeater_cls
    """

    generators = {}

    def __init__(self, repeater_cls, format_name, format_label, is_default=False):
        self.format_name = format_name
        self.format_label = format_label
        self.repeater_cls = repeater_cls
        self.label = format_label
        self.is_default = is_default

    def __call__(self, generator_class):
        if not self.repeater_cls in RegisterGenerator.generators:
            RegisterGenerator.generators[self.repeater_cls] = GeneratorCollection(self.repeater_cls)
        RegisterGenerator.generators[self.repeater_cls].add_new_format(
            self.format_name,
            self.format_label,
            generator_class,
            is_default=self.is_default
        )
        return generator_class

    @classmethod
    def generator_class_by_repeater_format(cls, repeater_class, format_name):
        """Return generator class given a Repeater class and format_name"""
        generator_collection = cls.generators[repeater_class]
        return generator_collection.get_generator_by_format(format_name)

    @classmethod
    def all_formats_by_repeater(cls, repeater_class, for_domain=None):
        """Return all formats for a given Repeater class"""
        generator_collection = cls.generators[repeater_class]
        return generator_collection.get_all_formats(for_domain=for_domain)

    @classmethod
    def default_format_by_repeater(cls, repeater_class):
        """Return default format_name for a Repeater class"""
        generator_collection = cls.generators[repeater_class]
        return generator_collection.get_default_format()


class Repeater(QuickCachedDocumentMixin, Document, UnicodeMixIn):
    """
    Represents the configuration of a repeater. Will specify the URL to forward to and
    other properties of the configuration.
    """
    base_doc = 'Repeater'

    domain = StringProperty()
    url = StringProperty()
    format = StringProperty()

    use_basic_auth = BooleanProperty(default=False)
    username = StringProperty()
    password = StringProperty()

    def get_pending_record_count(self):
        return get_pending_repeat_record_count(self.domain, self._id)

    def get_failure_record_count(self):
        return get_failure_repeat_record_count(self.domain, self._id)

    def get_success_record_count(self):
        return get_success_repeat_record_count(self.domain, self._id)

    def format_or_default_format(self):
        return self.format or RegisterGenerator.default_format_by_repeater(self.__class__)

    def get_payload_generator(self, payload_format):
        gen = RegisterGenerator.generator_class_by_repeater_format(self.__class__, payload_format)
        return gen(self)

    def payload_doc(self, repeat_record):
        raise NotImplementedError

    def get_payload(self, repeat_record):
        generator = self.get_payload_generator(self.format_or_default_format())
        return generator.get_payload(repeat_record, self.payload_doc(repeat_record))

    def register(self, payload, next_check=None):
        if not self.allowed_to_forward(payload):
            return

        repeat_record = RepeatRecord(
            repeater_id=self.get_id,
            repeater_type=self.doc_type,
            domain=self.domain,
            next_check=next_check or datetime.utcnow(),
            payload_id=payload.get_id
        )
        repeat_record.save()
        return repeat_record

    def allowed_to_forward(self, payload):
        """
        Return True/False depending on whether the payload meets forawrding criteria or not
        """
        return True

    def clear_caches(self):
        if self.__class__ == Repeater:
            cls = self.get_class_from_doc_type(self.doc_type)
        else:
            cls = self.__class__
        # clear cls.by_domain (i.e. filtered by doc type)
        Repeater.by_domain.clear(cls, self.domain)
        # clear Repeater.by_domain (i.e. not filtered by doc type)
        Repeater.by_domain.clear(Repeater, self.domain)

    @classmethod
    @quickcache(['cls.__name__', 'domain'], timeout=5 * 60, memoize_timeout=10)
    def by_domain(cls, domain):
        key = [domain]
        if cls.__name__ in repeater_types:
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
                if cls.get_class_from_doc_type(repeater_doc['doc']['doc_type'])]

    @classmethod
    def wrap(cls, data):
        if cls.__name__ == Repeater.__name__:
            cls_ = cls.get_class_from_doc_type(data['doc_type'])
            if cls_:
                return cls_.wrap(data)
            else:
                raise ResourceNotFound('Unknown repeater type: %s' % data)
        else:
            return super(Repeater, cls).wrap(data)

    @staticmethod
    def get_class_from_doc_type(doc_type):
        doc_type = doc_type.replace(DELETED, '')
        if doc_type in repeater_types:
            return repeater_types[doc_type]
        else:
            return None

    def retire(self):
        if DELETED not in self['doc_type']:
            self['doc_type'] += DELETED
        if DELETED not in self['base_doc']:
            self['base_doc'] += DELETED
        self.save()

    def get_url(self, repeate_record):
        # to be overridden
        return self.url

    def get_headers(self, repeat_record):
        # to be overridden
        generator = self.get_payload_generator(self.format_or_default_format())
        headers = generator.get_headers()
        if self.use_basic_auth:
            user_pass = base64.encodestring(':'.join((self.username, self.password))).replace('\n', '')
            headers.update({'Authorization': 'Basic ' + user_pass})

        return headers


@register_repeater_type
class FormRepeater(Repeater):
    """
    Record that forms should be repeated to a new url

    """

    include_app_id_param = BooleanProperty(default=True)

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    def allowed_to_forward(self, payload):
        return payload.xmlns != DEVICE_LOG_XMLNS

    def get_url(self, repeat_record):
        url = super(FormRepeater, self).get_url(repeat_record)
        if not self.include_app_id_param:
            return url
        else:
            # adapted from http://stackoverflow.com/a/2506477/10840
            url_parts = list(urlparse.urlparse(url))
            query = urlparse.parse_qsl(url_parts[4])
            query.append(("app_id", self.payload_doc(repeat_record).app_id))
            url_parts[4] = urllib.urlencode(query)
            return urlparse.urlunparse(url_parts)

    def get_headers(self, repeat_record):
        headers = super(FormRepeater, self).get_headers(repeat_record)
        headers.update({
            "received-on": self.payload_doc(repeat_record).received_on.isoformat()+"Z"
        })
        return headers

    def __unicode__(self):
        return "forwarding forms to: %s" % self.url


@register_repeater_type
class CaseRepeater(Repeater):
    """
    Record that cases should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)
    white_listed_case_types = StringListProperty(default=[])  # empty value means all case-types are accepted
    black_listed_users = StringListProperty(default=[])  # users who caseblock submissions should be ignored

    def allowed_to_forward(self, payload):
        allowed_case_type = not self.white_listed_case_types or payload.type in self.white_listed_case_types
        allowed_user = self.payload_user_id(payload) not in self.black_listed_users
        return allowed_case_type and allowed_user

    def payload_user_id(self, payload):
        # get the user_id who submitted the payload, note, it's not the owner_id
        return payload.actions[-1].user_id

    @memoized
    def payload_doc(self, repeat_record):
        return CaseAccessors(repeat_record.domain).get_case(repeat_record.payload_id)

    def get_headers(self, repeat_record):
        headers = super(CaseRepeater, self).get_headers(repeat_record)
        headers.update({
            "server-modified-on": self.payload_doc(repeat_record).server_modified_on.isoformat()+"Z"
        })
        return headers

    def __unicode__(self):
        return "forwarding cases to: %s" % self.url


@register_repeater_type
class ShortFormRepeater(Repeater):
    """
    Record that form id & case ids should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    def allowed_to_forward(self, payload):
        return payload.xmlns != DEVICE_LOG_XMLNS

    def get_headers(self, repeat_record):
        headers = super(ShortFormRepeater, self).get_headers(repeat_record)
        headers.update({
            "received-on": self.payload_doc(repeat_record).received_on.isoformat()+"Z"
        })
        return headers

    def __unicode__(self):
        return "forwarding short form to: %s" % self.url


@register_repeater_type
class AppStructureRepeater(Repeater):

    def payload_doc(self, repeat_record):
        return None


class RepeatRecord(Document):
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
    failure_reason = StringProperty()

    payload_id = StringProperty()

    @property
    @memoized
    def repeater(self):
        return Repeater.get(self.repeater_id)

    @property
    def url(self):
        try:
            return self.repeater.get_url(self)
        except XFormNotFound:
            return None

    @property
    def state(self):
        state = RECORD_PENDING_STATE
        if self.succeeded:
            state = RECORD_SUCCESS_STATE
        elif self.failure_reason:
            state = RECORD_FAILURE_STATE
        return state

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

    def update_failure(self, reason=None):
        # we use an exponential back-off to avoid submitting to bad urls
        # too frequently.
        assert self.succeeded is False
        assert self.next_check is not None
        now = datetime.utcnow()
        window = timedelta(minutes=0)
        if self.last_checked:
            window = self.next_check - self.last_checked
            window += (window // 2)  # window *= 1.5
        if window < MIN_RETRY_WAIT:
            window = MIN_RETRY_WAIT
        elif window > MAX_RETRY_WAIT:
            window = MAX_RETRY_WAIT

        self.last_checked = now
        self.next_check = self.last_checked + window
        self.failure_reason = reason

    def try_now(self):
        # try when we haven't succeeded and either we've
        # never checked, or it's time to check again
        return not self.succeeded

    def get_payload(self):
        return self.repeater.get_payload(self)

    def fire(self, max_tries=3, force_send=False):
        try:
            payload = self.get_payload()
        except ResourceNotFound:
            # this repeater is pointing at a missing document
            # quarantine it and tell it to stop trying.
            logging.exception(u'Repeater {} in domain {} references a missing or deleted document!'.format(
                self._id, self.domain,
            ))
            self.doc_type = self.doc_type + '-Failed'
            self.save()
        except IgnoreDocument:
            # this repeater is pointing at a document with no payload
            logging.info(u'Repeater {} in domain {} references a document with no payload'.format(
                self._id, self.domain,
            ))
            # Mark it succeeded so that we don't try again
            self.update_success()
        else:
            headers = self.repeater.get_headers(self)
            if self.try_now() or force_send:
                # we don't use celery's version of retry because
                # we want to override the success/fail each try
                failure_reason = None
                for i in range(max_tries):
                    try:
                        resp = simple_post_with_cached_timeout(
                            payload,
                            self.url,
                            headers=headers,
                            force_send=force_send,
                            timeout=POST_TIMEOUT,
                        )
                        if 200 <= resp.status_code < 300:
                            self.update_success()
                            break
                        else:
                            failure_reason = u'{}: {}'.format(resp.status_code, resp.reason)
                    except Exception, e:
                        failure_reason = unicode(e)

                if not self.succeeded:
                    # mark it failed for later and give up
                    self.update_failure(failure_reason)
                    log_counter(REPEATER_ERROR_COUNT, {
                        '_id': self._id,
                        'reason': failure_reason,
                        'target_url': self.url,
                    })

# import signals
# Do not remove this import, its required for the signals code to run even though not explicitly used in this file
from corehq.apps.repeaters import signals
