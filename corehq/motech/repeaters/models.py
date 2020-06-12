"""
Repeaters
=========

Repeaters forward payloads to remote API endpoints over HTTP(S),
typically in JSON- or XML-formatted requests.


Custom Repeaters
----------------

Custom repeaters subclass ``Repeater``. They allow custom payloads to be
created that can compile data from multiple sources and be sent as
JSON or XML. Custom triggers for when to send this data can also be
defined. These triggers are run whenever the model in question (case,
form, or application) is changed.


How Do They Work?
-----------------

A good place to start is *signals.py*. From the bottom of the file you
can see that a repeat record is created when a form is received, or
after a case or user or location is saved.

The ``create_repeat_records()`` function will iterate through the
instances of a given subclass of ``Repeater`` that are configured for
the domain. For example, after a case has been saved,
``create_repeat_records()`` is called with ``CaseRepeater``, then
``CreateCaseRepeater`` and then ``UpdateCaseRepeater``. A domain can
have many case repeaters configured to forward case changes to different
URLs (or the same URL with different credentials). The ``register()``
method of each of the domain's case repeaters will be called with the
case as its payload.

The same applies to forms that are received, or users or locations that
are saved.

The ``register()`` method creates a ``RepeatRecord`` instance, and
associates it with the payload using the payload's ID. The
``RepeatRecord.next_check`` property is set to ``datetime.utcnow()``.

Next we jump to *tasks.py*. The ``check_repeaters()`` function will run
every ``CHECK_REPEATERS_INTERVAL`` (currently set to 5 minutes). Each
``RepeatRecord`` due to be processed will be added to the
``CELERY_REPEAT_RECORD_QUEUE``.

When it is pulled off the queue and processed, if its repeater is paused
it will be postponed. If its repeater is deleted it will be deleted. And
if it is waiting to be sent, or resent, its ``fire()`` method will be
called, which will call its repeater's ``fire_for_record()`` method.

The repeater will transform the payload into the right format for the
repeater's subclass type and configuration, and then send the
transformed data to the repeater's destination URL.

The response from the destination will be handled according to whether
the request succeeded, failed, or raised an exception. It will create a
``RepeatRecordAttempt``, and may include other actions depending on the
class.

``RepeatRecordAttempt`` instances are listed under "Project Settings" >
"Data Forwarding Records".

"""
import re
import warnings
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.utils.translation import ugettext_lazy as _

from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from memoized import memoized
from requests.exceptions import ConnectionError, Timeout

from casexml.apps.case.xml import LEGAL_VERSIONS, V2
from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    ListProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.parsing import json_format_datetime

from corehq import toggles
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.motech.auth import (
    AuthManager,
    BasicAuthManager,
    BearerAuthManager,
    DigestAuthManager,
)
from corehq.motech.const import (
    ALGO_AES,
    BASIC_AUTH,
    BEARER_AUTH,
    DIGEST_AUTH,
    OAUTH1,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import Requests, simple_post
from corehq.motech.utils import b64_aes_decrypt
from corehq.util.metrics import metrics_counter
from corehq.util.quickcache import quickcache

from .const import (
    MAX_RETRY_WAIT,
    MIN_RETRY_WAIT,
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
)
from .dbaccessors import (
    get_cancelled_repeat_record_count,
    get_failure_repeat_record_count,
    get_pending_repeat_record_count,
    get_success_repeat_record_count,
)
from .exceptions import RequestConnectionError
from .repeater_generators import (
    AppStructureGenerator,
    CaseRepeaterJsonPayloadGenerator,
    CaseRepeaterXMLPayloadGenerator,
    FormRepeaterJsonPayloadGenerator,
    FormRepeaterXMLPayloadGenerator,
    LocationPayloadGenerator,
    ReferCasePayloadGenerator,
    ShortFormRepeaterJsonPayloadGenerator,
    UserPayloadGenerator,
)
from .utils import get_all_repeater_types


def log_repeater_timeout_in_datadog(domain):
    metrics_counter('commcare.repeaters.timeout', tags={'domain': domain})


def log_repeater_error_in_datadog(domain, status_code, repeater_type):
    metrics_counter('commcare.repeaters.error', tags={
        'domain': domain,
        'status_code': status_code,
        'repeater_type': repeater_type,
    })


def log_repeater_success_in_datadog(domain, status_code, repeater_type):
    metrics_counter('commcare.repeaters.success', tags={
        'domain': domain,
        'status_code': status_code,
        'repeater_type': repeater_type,
    })


class Repeater(QuickCachedDocumentMixin, Document):
    """
    Represents the configuration of a repeater. Will specify the URL to forward to and
    other properties of the configuration.
    """
    base_doc = 'Repeater'

    domain = StringProperty()

    connection_settings_id = IntegerProperty(required=False, default=None)
    # TODO: Delete the following properties once all Repeaters have been
    #       migrated to ConnectionSettings. (2020-05-16)
    url = StringProperty()
    auth_type = StringProperty(choices=(BASIC_AUTH, DIGEST_AUTH, OAUTH1, BEARER_AUTH), required=False)
    username = StringProperty()
    password = StringProperty()  # See also plaintext_password()
    skip_cert_verify = BooleanProperty(default=False)  # See also verify()
    notify_addresses_str = StringProperty(default="")  # See also notify_addresses()

    format = StringProperty()
    friendly_name = _("Data")
    paused = BooleanProperty(default=False)

    payload_generator_classes = ()

    _has_config = False

    def __str__(self):
        url = "@".join((self.username, self.url)) if self.username else self.url
        return f"<{self.__class__.__name__} {self._id} {url}>"

    @property
    def connection_settings(self):
        if not self.connection_settings_id:
            return self.create_connection_settings()
        return ConnectionSettings.objects.get(pk=self.connection_settings_id)

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

    def get_cancelled_record_count(self):
        return get_cancelled_repeat_record_count(self.domain, self._id)

    def _format_or_default_format(self):
        from corehq.motech.repeaters.repeater_generators import RegisterGenerator
        return self.format or RegisterGenerator.default_format_by_repeater(self.__class__)

    def _get_payload_generator(self, payload_format):
        from corehq.motech.repeaters.repeater_generators import RegisterGenerator
        gen = RegisterGenerator.generator_class_by_repeater_format(self.__class__, payload_format)
        return gen(self)

    @property
    @memoized
    def generator(self):
        return self._get_payload_generator(self._format_or_default_format())

    def payload_doc(self, repeat_record):
        raise NotImplementedError

    @memoized
    def get_payload(self, repeat_record):
        return self.generator.get_payload(repeat_record, self.payload_doc(repeat_record))

    def get_attempt_info(self, repeat_record):
        return None

    def register(self, payload, next_check=None):
        if not self.allowed_to_forward(payload):
            return

        now = datetime.utcnow()
        repeat_record = RepeatRecord(
            repeater_id=self.get_id,
            repeater_type=self.doc_type,
            domain=self.domain,
            registered_on=now,
            next_check=next_check or now,
            payload_id=payload.get_id
        )
        repeat_record.save()
        if next_check is None:
            repeat_record.attempt_forward_now()
        return repeat_record

    def allowed_to_forward(self, payload):
        """
        Return True/False depending on whether the payload meets forawrding criteria or not
        """
        return True

    def clear_caches(self):
        super(Repeater, self).clear_caches()
        # Also expire for cases repeater is fetched using Repeater class.
        # The quick cache called in clear_cache also check on relies of doc class
        # so in case the class is set as Repeater it is not expired like in edit forms.
        # So expire it explicitly here with Repeater class as well.
        Repeater.get.clear(Repeater, self._id)
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

        raw_docs = cls.view('repeaters/repeaters',
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
        doc_type = doc_type.replace(DELETED_SUFFIX, '')
        repeater_types = get_all_repeater_types()
        if doc_type in repeater_types:
            return repeater_types[doc_type]
        else:
            return None

    def retire(self):
        if DELETED_SUFFIX not in self['doc_type']:
            self['doc_type'] += DELETED_SUFFIX
        if DELETED_SUFFIX not in self['base_doc']:
            self['base_doc'] += DELETED_SUFFIX
        self.paused = False
        self.save()

    def pause(self):
        self.paused = True
        self.save()

    def resume(self):
        self.paused = False
        self.save()

    def get_url(self, repeat_record):
        # to be overridden
        return self.connection_settings.url

    def allow_retries(self, response):
        """Whether to requeue the repeater when it fails
        """
        return True

    def get_headers(self, repeat_record):
        # to be overridden
        return self.generator.get_headers()

    @property
    def plaintext_password(self):
        if self.password.startswith('${algo}$'.format(algo=ALGO_AES)):
            ciphertext = self.password.split('$', 2)[2]
            return b64_aes_decrypt(ciphertext)
        return self.password

    def get_auth_manager(self):
        if self.auth_type is None:
            return AuthManager()
        if self.auth_type == BASIC_AUTH:
            return BasicAuthManager(
                self.username,
                self.password,
            )
        if self.auth_type == DIGEST_AUTH:
            return DigestAuthManager(
                self.username,
                self.password,
            )
        if self.auth_type == OAUTH1:
            raise NotImplementedError(_(
                'OAuth1 authentication workflow not yet supported.'
            ))
        if self.auth_type == BEARER_AUTH:
            return BearerAuthManager(
                self.username,
                self.password,
            )
        # OAuth 2.0 coming when Repeaters use ConnectionSettings

    @property
    def verify(self):
        return not self.skip_cert_verify

    @property
    def notify_addresses(self):
        return [addr for addr in re.split('[, ]+', self.notify_addresses_str) if addr]

    def send_request(self, repeat_record, payload):
        url = self.get_url(repeat_record)
        return simple_post(
            self.domain, url, payload,
            headers=self.get_headers(repeat_record),
            auth_manager=self.get_auth_manager(),
            verify=self.verify,
            notify_addresses=self.notify_addresses,
            payload_id=repeat_record.payload_id,
        )

    def fire_for_record(self, repeat_record):
        payload = self.get_payload(repeat_record)
        try:
            response = self.send_request(repeat_record, payload)
        except (Timeout, ConnectionError) as error:
            log_repeater_timeout_in_datadog(self.domain)
            return self.handle_response(RequestConnectionError(error), repeat_record)
        except Exception as e:
            return self.handle_response(e, repeat_record)
        else:
            return self.handle_response(response, repeat_record)

    def handle_response(self, result, repeat_record):
        """
        route the result to the success, failure, or exception handlers

        result may be either a response object or an exception
        """
        if isinstance(result, Exception):
            attempt = repeat_record.handle_exception(result)
            self.generator.handle_exception(result, repeat_record)
        elif _is_response(result) and 200 <= result.status_code < 300 or result is True:
            attempt = repeat_record.handle_success(result)
            self.generator.handle_success(result, self.payload_doc(repeat_record), repeat_record)
        else:
            attempt = repeat_record.handle_failure(result)
            self.generator.handle_failure(result, self.payload_doc(repeat_record), repeat_record)
        return attempt

    @property
    def form_class_name(self):
        """
        Return the name of the class whose edit form this class uses.

        (Most classes that extend CaseRepeater, and all classes that
        extend FormRepeater, use the same form.)
        """
        return self.__class__.__name__

    def create_connection_settings(self):
        if self.connection_settings_id:
            return  # Nothing to do
        conn = ConnectionSettings(
            domain=self.domain,
            name=self.url,
            url=self.url,
            auth_type=self.auth_type,
            username=self.username,
            skip_cert_verify=self.skip_cert_verify,
            notify_addresses_str=self.notify_addresses_str,
        )
        # Allow ConnectionSettings to encrypt old Repeater passwords:
        conn.plaintext_password = self.plaintext_password
        conn.save()
        self.connection_settings_id = conn.id
        self.save()
        return conn


class FormRepeater(Repeater):
    """
    Record that forms should be repeated to a new url

    """

    payload_generator_classes = (FormRepeaterXMLPayloadGenerator, FormRepeaterJsonPayloadGenerator)

    include_app_id_param = BooleanProperty(default=True)
    white_listed_form_xmlns = StringListProperty(default=[])  # empty value means all form xmlns are accepted
    friendly_name = _("Forward Forms")

    @memoized
    def payload_doc(self, repeat_record):
        return FormAccessors(repeat_record.domain).get_form(repeat_record.payload_id)

    @property
    def form_class_name(self):
        """
        FormRepeater and its subclasses use the same form for editing
        """
        return 'FormRepeater'

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
            url_parts = list(urlparse(url))
            query = parse_qsl(url_parts[4])
            try:
                query.append(("app_id", self.payload_doc(repeat_record).app_id))
            except (XFormNotFound, ResourceNotFound):
                return None
            url_parts[4] = urlencode(query)
            return urlunparse(url_parts)

    def get_headers(self, repeat_record):
        headers = super(FormRepeater, self).get_headers(repeat_record)
        headers.update({
            "received-on": self.payload_doc(repeat_record).received_on.isoformat()+"Z"
        })
        return headers

    def __str__(self):
        return "forwarding forms to: %s" % self.url


class CaseRepeater(Repeater):
    """
    Record that cases should be repeated to a new url

    """

    payload_generator_classes = (CaseRepeaterXMLPayloadGenerator, CaseRepeaterJsonPayloadGenerator)

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

    @property
    def form_class_name(self):
        """
        CaseRepeater and most of its subclasses use the same form for editing
        """
        return 'CaseRepeater'

    def get_headers(self, repeat_record):
        headers = super(CaseRepeater, self).get_headers(repeat_record)
        headers.update({
            "server-modified-on": self.payload_doc(repeat_record).server_modified_on.isoformat()+"Z"
        })
        return headers

    def __str__(self):
        return "forwarding cases to: %s" % self.url


class CreateCaseRepeater(CaseRepeater):
    """
    Just like CaseRepeater but only create records if the case is being created.
    Used by the Zapier integration.
    """
    friendly_name = _("Forward Cases on Creation Only")

    def allowed_to_forward(self, payload):
        # assume if there's exactly 1 xform_id that modified the case it's being created
        return super(CreateCaseRepeater, self).allowed_to_forward(payload) and len(payload.xform_ids) == 1


class UpdateCaseRepeater(CaseRepeater):
    """
    Just like CaseRepeater but only create records if the case is being updated.
    Used by the Zapier integration.
    """
    friendly_name = _("Forward Cases on Update Only")

    def allowed_to_forward(self, payload):
        return super(UpdateCaseRepeater, self).allowed_to_forward(payload) and len(payload.xform_ids) > 1


class ReferCaseRepeater(CreateCaseRepeater):
    """
    A repeater that triggers off case creation but sends a form creating cases in
    another commcare project
    """
    friendly_name = _("Forward Cases To Another Commcare Project")

    payload_generator_classes = (ReferCasePayloadGenerator,)

    def form_class_name(self):
        # Note this class does not exist but this property is only used to construct the URL
        return 'ReferCaseRepeater'

    @classmethod
    def available_for_domain(cls, domain):
        """Returns whether this repeater can be used by a particular domain
        """
        return toggles.REFER_CASE_REPEATER.enabled(domain)

    def get_url(self, repeat_record):
        new_domain = self.payload_doc(repeat_record).get_case_property('new_domain')
        return self.connection_settings.url.format(domain=new_domain)


class ShortFormRepeater(Repeater):
    """
    Record that form id & case ids should be repeated to a new url

    """

    version = StringProperty(default=V2, choices=LEGAL_VERSIONS)
    friendly_name = _("Forward Form Stubs")

    payload_generator_classes = (ShortFormRepeaterJsonPayloadGenerator,)

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

    def __str__(self):
        return "forwarding short form to: %s" % self.url


class AppStructureRepeater(Repeater):
    friendly_name = _("Forward App Schema Changes")

    payload_generator_classes = (AppStructureGenerator,)

    def payload_doc(self, repeat_record):
        return None


class UserRepeater(Repeater):
    friendly_name = _("Forward Users")

    payload_generator_classes = (UserPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        return CommCareUser.get(repeat_record.payload_id)

    def __str__(self):
        return "forwarding users to: %s" % self.url


class LocationRepeater(Repeater):
    friendly_name = _("Forward Locations")

    payload_generator_classes = (LocationPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        return SQLLocation.objects.get(location_id=repeat_record.payload_id)

    def __str__(self):
        return "forwarding locations to: %s" % self.url


class RepeatRecordAttempt(DocumentSchema):
    cancelled = BooleanProperty(default=False)
    datetime = DateTimeProperty()
    failure_reason = StringProperty()
    success_response = StringProperty()
    next_check = DateTimeProperty()
    succeeded = BooleanProperty(default=False)
    info = StringProperty()     # extra information about this attempt

    @property
    def message(self):
        return self.success_response if self.succeeded else self.failure_reason


class RepeatRecord(Document):
    """
    An record of a particular instance of something that needs to be forwarded
    with a link to the proper repeater object
    """

    domain = StringProperty()
    repeater_id = StringProperty()
    repeater_type = StringProperty()
    payload_id = StringProperty()

    overall_tries = IntegerProperty(default=0)
    max_possible_tries = IntegerProperty(default=6)

    attempts = ListProperty(RepeatRecordAttempt)

    cancelled = BooleanProperty(default=False)
    registered_on = DateTimeProperty()
    last_checked = DateTimeProperty()
    failure_reason = StringProperty()
    next_check = DateTimeProperty()
    succeeded = BooleanProperty(default=False)

    @property
    def record_id(self):
        return self._id

    @classmethod
    def wrap(cls, data):
        should_bootstrap_attempts = ('attempts' not in data)

        self = super(RepeatRecord, cls).wrap(data)

        if should_bootstrap_attempts and self.last_checked:
            assert not self.attempts
            self.attempts = [RepeatRecordAttempt(
                cancelled=self.cancelled,
                datetime=self.last_checked,
                failure_reason=self.failure_reason,
                success_response=None,
                next_check=self.next_check,
                succeeded=self.succeeded,
            )]
        return self

    @property
    @memoized
    def repeater(self):
        try:
            return Repeater.get(self.repeater_id)
        except ResourceNotFound:
            return None

    @property
    def url(self):
        warnings.warn("RepeatRecord.url is deprecated. Use Repeater.get_url instead", DeprecationWarning)
        if self.repeater:
            return self.repeater.get_url(self)

    @property
    def state(self):
        state = RECORD_PENDING_STATE
        if self.succeeded:
            state = RECORD_SUCCESS_STATE
        elif self.cancelled:
            state = RECORD_CANCELLED_STATE
        elif self.failure_reason:
            state = RECORD_FAILURE_STATE
        return state

    @classmethod
    def all(cls, domain=None, due_before=None, limit=None):
        json_now = json_format_datetime(due_before or datetime.utcnow())
        repeat_records = RepeatRecord.view("repeaters/repeat_records_by_next_check",
            startkey=[domain],
            endkey=[domain, json_now, {}],
            include_docs=True,
            reduce=False,
            limit=limit,
        )
        return repeat_records

    @classmethod
    def count(cls, domain=None):
        results = RepeatRecord.view("repeaters/repeat_records_by_next_check",
            startkey=[domain],
            endkey=[domain, {}],
            reduce=True,
        ).one()
        return results['value'] if results else 0

    def add_attempt(self, attempt):
        self.attempts.append(attempt)
        self.last_checked = attempt.datetime
        self.next_check = attempt.next_check
        self.succeeded = attempt.succeeded
        self.cancelled = attempt.cancelled
        self.failure_reason = attempt.failure_reason

    def get_numbered_attempts(self):
        for i, attempt in enumerate(self.attempts):
            yield i + 1, attempt

    def postpone_by(self, duration):
        self.last_checked = datetime.utcnow()
        self.next_check = self.last_checked + duration
        self.save()

    def make_set_next_try_attempt(self, failure_reason):
        assert self.succeeded is False
        assert self.next_check is not None
        now = datetime.utcnow()
        return RepeatRecordAttempt(
            cancelled=False,
            datetime=now,
            failure_reason=failure_reason,
            success_response=None,
            next_check=now + _get_retry_interval(self.last_checked, now),
            succeeded=False,
        )

    def try_now(self):
        # try when we haven't succeeded and either we've
        # never checked, or it's time to check again
        return not self.succeeded

    def get_payload(self):
        return self.repeater.get_payload(self)

    def get_attempt_info(self):
        return self.repeater.get_attempt_info(self)

    def handle_payload_exception(self, exception):
        now = datetime.utcnow()
        return RepeatRecordAttempt(
            cancelled=True,
            datetime=now,
            failure_reason=str(exception),
            success_response=None,
            next_check=None,
            succeeded=False,
        )

    def fire(self, force_send=False):
        if self.try_now() or force_send:
            self.overall_tries += 1
            try:
                attempt = self.repeater.fire_for_record(self)
            except Exception as e:
                log_repeater_error_in_datadog(self.domain, status_code=None,
                                              repeater_type=self.repeater_type)
                attempt = self.handle_payload_exception(e)
                raise
            finally:
                # pycharm warns attempt might not be defined.
                # that'll only happen if fire_for_record raise a non-Exception exception (e.g. SIGINT)
                # or handle_payload_exception raises an exception. I'm okay with that. -DMR
                self.add_attempt(attempt)
                self.save()

    @staticmethod
    def _format_response(response):
        if not _is_response(response):
            return None
        response_body = getattr(response, "text", "")
        return '{}: {}.\n{}'.format(
            response.status_code, response.reason, response_body)

    def handle_success(self, response):
        """
        Log success in Datadog and return a success RepeatRecordAttempt.

        ``response`` can be a Requests response instance, or True if the
        payload did not result in an API call.
        """
        now = datetime.utcnow()
        if _is_response(response):
            # ^^^ Don't bother logging success in Datadog if the payload
            # did not need to be sent. (This can happen with DHIS2 if
            # the form that triggered the forwarder doesn't contain data
            # for a DHIS2 Event.)
            log_repeater_success_in_datadog(
                self.domain,
                response.status_code,
                self.repeater_type
            )
        return RepeatRecordAttempt(
            cancelled=False,
            datetime=now,
            failure_reason=None,
            success_response=self._format_response(response),
            next_check=None,
            succeeded=True,
            info=self.get_attempt_info(),
        )

    def handle_failure(self, response):
        """Do something with the response if the repeater fails
        """
        return self._make_failure_attempt(self._format_response(response), response)

    def handle_exception(self, exception):
        """handle internal exceptions
        """
        return self._make_failure_attempt(str(exception), None)

    def _make_failure_attempt(self, reason, response):
        log_repeater_error_in_datadog(self.domain, response.status_code if response else None,
                                      self.repeater_type)

        if self.repeater.allow_retries(response) and self.overall_tries < self.max_possible_tries:
            return self.make_set_next_try_attempt(reason)
        else:
            now = datetime.utcnow()
            return RepeatRecordAttempt(
                cancelled=True,
                datetime=now,
                failure_reason=reason,
                success_response=None,
                next_check=None,
                succeeded=False,
                info=self.get_attempt_info(),
            )

    def cancel(self):
        self.next_check = None
        self.cancelled = True

    def attempt_forward_now(self):
        from corehq.motech.repeaters.tasks import process_repeat_record

        def is_ready():
            return self.next_check < datetime.utcnow()

        def already_processed():
            return self.succeeded or self.cancelled or self.next_check is None

        if already_processed() or not is_ready():
            return

        # Set the next check to happen an arbitrarily long time from now so
        # if something goes horribly wrong with the delayed task it will not
        # be lost forever. A check at this time is expected to occur rarely,
        # if ever, because `process_repeat_record` will usually succeed or
        # reset the next check to sometime sooner.
        self.next_check = datetime.utcnow() + timedelta(hours=48)
        try:
            self.save()
        except ResourceConflict:
            # Another process beat us to the punch. This takes advantage
            # of Couch DB's optimistic locking, which prevents a process
            # with stale data from overwriting the work of another.
            return
        process_repeat_record.delay(self)

    def requeue(self):
        self.cancelled = False
        self.succeeded = False
        self.failure_reason = ''
        self.overall_tries = 0
        self.next_check = datetime.utcnow()


def _get_retry_interval(last_checked, now):
    """
    Returns a timedelta between MIN_RETRY_WAIT and MAX_RETRY_WAIT that
    is roughly three times as long as the previous interval.

    We use an exponential back-off to avoid submitting to bad URLs
    too frequently. Retries will typically be after 1h, 3h, 9h, 27h,
    81h, so that the last attempt will be at least 5d 1h after the
    first attempt.
    """
    if last_checked:
        interval = 3 * (now - last_checked)
    else:
        interval = timedelta(0)
    interval = max(MIN_RETRY_WAIT, interval)
    interval = min(MAX_RETRY_WAIT, interval)
    return interval


def _is_response(duck):
    """
    Returns True if ``duck`` has the attributes of a Requests response
    instance that this module uses, otherwise False.
    """
    return hasattr(duck, 'status_code') and hasattr(duck, 'reason')


# import signals
# Do not remove this import, its required for the signals code to run even though not explicitly used in this file
from corehq.motech.repeaters import signals  # pylint: disable=unused-import,F401
