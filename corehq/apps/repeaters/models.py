import base64
from collections import namedtuple
from datetime import datetime, timedelta
import logging
import urllib
import urlparse
from django.utils.translation import ugettext_lazy as _

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
from .utils import get_all_repeater_types


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
        message = u'Status Code {}: {}. {}'.format(resp.status_code, resp.reason, getattr(resp, 'content', None))
        cache.set(key, message, expiry)

    return resp


DELETED = "-Deleted"

FormatInfo = namedtuple('FormatInfo', 'name label generator_class')
PostInfo = namedtuple('PostInfo', 'payload headers force_send max_tries')


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
    friendly_name = _("Data")

    @classmethod
    def get_custom_url(cls, domain):
        return None

    @classmethod
    def available_for_domain(cls, domain):
        """Returns whether this repeater can be used by a particular domain
        """
        return True

    def get_pending_record_count(self):
        return get_pending_repeat_record_count(self.domain, self._id)

    def get_failure_record_count(self):
        return get_failure_repeat_record_count(self.domain, self._id)

    def get_success_record_count(self):
        return get_success_repeat_record_count(self.domain, self._id)

    def format_or_default_format(self):
        from corehq.apps.repeaters.repeater_generators import RegisterGenerator
        return self.format or RegisterGenerator.default_format_by_repeater(self.__class__)

    def get_payload_generator(self, payload_format):
        from corehq.apps.repeaters.repeater_generators import RegisterGenerator
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
        if cls.__name__ in get_all_repeater_types():
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
        repeater_types = get_all_repeater_types()
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

    def allow_retries(self, response):
        """Whether to requeue the repeater when it fails
        """
        return True

    def allow_immediate_retries(self, response):
        """Whether to retry failed requests immediately a few times
        """
        return True

    def get_headers(self, repeat_record):
        # to be overridden
        generator = self.get_payload_generator(self.format_or_default_format())
        headers = generator.get_headers()
        if self.use_basic_auth:
            user_pass = base64.encodestring(':'.join((self.username, self.password))).replace('\n', '')
            headers.update({'Authorization': 'Basic ' + user_pass})

        return headers

    def handle_success(self, response, repeat_record):
        """handle a successful post
        """
        generator = self.get_payload_generator(self.format_or_default_format())
        return generator.handle_success(response, self.payload_doc(repeat_record), repeat_record)

    def handle_failure(self, response, repeat_record):
        """handle a failed post
        """
        generator = self.get_payload_generator(self.format_or_default_format())
        return generator.handle_failure(response, self.payload_doc(repeat_record), repeat_record)

    def handle_exception(self, exception, repeat_record):
        """handle an exception during a post
        """
        generator = self.get_payload_generator(self.format_or_default_format())
        return generator.handle_exception(exception, repeat_record)


class FormRepeater(Repeater):
    """
    Record that forms should be repeated to a new url

    """

    include_app_id_param = BooleanProperty(default=True)
    white_listed_form_xmlns = StringListProperty(default=[])  # empty value means all form xmlns are accepted
    friendly_name = _("Forward Forms")

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    def allowed_to_forward(self, payload):
        return (
            payload.xmlns != DEVICE_LOG_XMLNS and
            (not self.white_listed_form_xmlns or payload.xmlns in self.white_listed_form_xmlns)
        )

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


class CaseRepeater(Repeater):
    """
    Record that cases should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)
    white_listed_case_types = StringListProperty(default=[])  # empty value means all case-types are accepted
    black_listed_users = StringListProperty(default=[])  # users who caseblock submissions should be ignored
    friendly_name = _("Forward Cases")

    def allowed_to_forward(self, payload):
        return self._allowed_case_type(payload) and self._allowed_user(payload)

    def _allowed_case_type(self, payload):
        return not self.white_listed_case_types or payload.type in self.white_listed_case_types

    def _allowed_user(self, payload):
        return self.payload_user_id(payload) not in self.black_listed_users

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


class ShortFormRepeater(Repeater):
    """
    Record that form id & case ids should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)
    friendly_name = _("Forward Form Stubs")

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


class AppStructureRepeater(Repeater):
    friendly_name = _("Forward App Schema Changes")

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
        except (XFormNotFound, ResourceNotFound):
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

    def set_next_try(self, reason=None):
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

    def try_now(self):
        # try when we haven't succeeded and either we've
        # never checked, or it's time to check again
        return not self.succeeded

    def get_payload(self):
        try:
            return self.repeater.get_payload(self)
        except ResourceNotFound as e:
            # this repeater is pointing at a missing document
            # quarantine it and tell it to stop trying.
            logging.exception(
                u'Repeater {} in domain {} references a missing or deleted document!'.format(
                    self._id, self.domain,
                ))

            self._payload_exception(e, reraise=False)
        except IgnoreDocument:
            # this repeater is pointing at a document with no payload
            logging.info(u'Repeater {} in domain {} references a document with no payload'.format(
                self._id, self.domain,
            ))
            # Mark it succeeded so that we don't try again
            self.update_success()
        except Exception as e:
            self._payload_exception(e, reraise=True)

    def _payload_exception(self, exception, reraise=False):
        self.doc_type = self.doc_type + '-Failed'
        self.failure_reason = unicode(exception)
        self.save()
        if reraise:
            raise

    def fire(self, max_tries=3, force_send=False):
        headers = self.repeater.get_headers(self)
        if self.try_now() or force_send:
            tries = 0
            post_info = PostInfo(self.get_payload(), headers, force_send, max_tries)
            self.post(post_info, tries=tries)

    def post(self, post_info, tries=0):
        tries += 1
        try:
            response = simple_post_with_cached_timeout(
                post_info.payload,
                self.url,
                headers=post_info.headers,
                force_send=post_info.force_send,
                timeout=POST_TIMEOUT,
            )
        except Exception, e:
            self.handle_exception(e)
        else:
            return self.handle_response(response, post_info, tries)

    def handle_response(self, response, post_info, tries):
        if 200 <= response.status_code < 300:
            return self.handle_success(response)
        else:
            return self.handle_failure(response, post_info, tries)

    def handle_success(self, response):
        """Do something with the response if the repeater succeeds
        """
        self.last_checked = datetime.utcnow()
        self.next_check = None
        self.succeeded = True
        self.repeater.handle_success(response, self)

    def handle_failure(self, response, post_info, tries):
        """Do something with the response if the repeater fails
        """
        if tries < post_info.max_tries and self.repeater.allow_immediate_retries(response):
            return self.post(post_info, tries)
        else:
            self._fail(u'{}: {}'.format(response.status_code, response.reason), response)
            self.repeater.handle_failure(response, self)

    def handle_exception(self, exception):
        """handle internal exceptions
        """
        self._fail(unicode(exception), None)
        self.repeater.handle_exception(exception, self)

    def _fail(self, reason, response):
        if self.repeater.allow_retries(response):
            self.set_next_try()
        self.failure_reason = reason
        log_counter(REPEATER_ERROR_COUNT, {
            '_id': self._id,
            'reason': reason,
            'target_url': self.url,
        })

# import signals
# Do not remove this import, its required for the signals code to run even though not explicitly used in this file
from corehq.apps.repeaters import signals
