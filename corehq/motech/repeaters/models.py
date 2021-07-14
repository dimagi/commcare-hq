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
import traceback
import warnings
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from memoized import memoized
from requests.exceptions import ConnectionError, Timeout, RequestException

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
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function
from dimagi.utils.parsing import json_format_datetime

from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.motech.const import (
    ALGO_AES,
    BASIC_AUTH,
    BEARER_AUTH,
    DIGEST_AUTH,
    OAUTH1,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import simple_post
from corehq.motech.utils import b64_aes_decrypt
from corehq.privileges import DATA_FORWARDING, ZAPIER_INTEGRATION
from corehq.util.couch import stale_ok
from corehq.util.metrics import metrics_counter
from corehq.util.quickcache import quickcache

from .const import (
    MAX_ATTEMPTS,
    MAX_BACKOFF_ATTEMPTS,
    MAX_RETRY_WAIT,
    MIN_RETRY_WAIT,
    RECORD_CANCELLED_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_STATES,
    RECORD_SUCCESS_STATE,
)
from .dbaccessors import (
    force_update_repeaters_views,
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
from ..repeater_helpers import RepeaterResponse
from ...util.urlvalidate.urlvalidate import PossibleSSRFAttempt


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


class RepeaterStubManager(models.Manager):

    def all_ready(self):
        """
        Return all RepeaterStubs ready to be forwarded.
        """
        not_paused = models.Q(is_paused=False)
        next_attempt_not_in_the_future = (
            models.Q(next_attempt_at__isnull=True)
            | models.Q(next_attempt_at__lte=timezone.now())
        )
        repeat_records_ready_to_send = models.Q(
            repeat_records__state__in=(RECORD_PENDING_STATE,
                                       RECORD_FAILURE_STATE)
        )
        return (self.get_queryset()
                .filter(not_paused)
                .filter(next_attempt_not_in_the_future)
                .filter(repeat_records_ready_to_send))


class RepeaterStub(models.Model):
    """
    This model links the SQLRepeatRecords of a Repeater.
    """
    domain = models.CharField(max_length=126)
    repeater_id = models.CharField(max_length=36)
    is_paused = models.BooleanField(default=False)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    objects = RepeaterStubManager()

    class Meta:
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['repeater_id']),
        ]

    @property
    @memoized
    def repeater(self):
        return Repeater.get(self.repeater_id)

    @property
    def repeat_records_ready(self):
        return self.repeat_records.filter(state__in=(RECORD_PENDING_STATE,
                                                     RECORD_FAILURE_STATE))

    @property
    def is_ready(self):
        if self.is_paused:
            return False
        if not (self.next_attempt_at is None
                or self.next_attempt_at < timezone.now()):
            return False
        return self.repeat_records_ready.exists()

    def set_next_attempt(self):
        now = datetime.utcnow()
        interval = _get_retry_interval(self.last_attempt_at, now)
        self.last_attempt_at = now
        self.next_attempt_at = now + interval
        self.save()

    def reset_next_attempt(self):
        if self.last_attempt_at or self.next_attempt_at:
            self.last_attempt_at = None
            self.next_attempt_at = None
            self.save()


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

    # TODO: Use to collect stats to determine whether remote endpoint is valid
    started_at = DateTimeProperty(default=datetime.utcnow)
    last_success_at = DateTimeProperty(required=False, default=None)
    failure_streak = IntegerProperty(default=0)

    payload_generator_classes = ()

    _has_config = False

    def __str__(self):
        return f'{self.__class__.__name__}: {self.name}'

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._id} {self.name!r}>"

    @property
    def connection_settings(self):
        if not self.connection_settings_id:
            return self.create_connection_settings()
        return self._get_connection_settings()

    # Cache across instances to avoid N+1 query problem when calling
    # Repeater.get_url() for each row in repeat record report
    @quickcache(['self.connection_settings_id'])
    def _get_connection_settings(self):
        return ConnectionSettings.objects.get(pk=self.connection_settings_id)

    @property
    def name(self):
        return self.connection_settings.name

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

    def register(self, payload):
        if not self.allowed_to_forward(payload):
            return

        now = datetime.utcnow()
        repeat_record = RepeatRecord(
            repeater_id=self.get_id,
            repeater_type=self.doc_type,
            domain=self.domain,
            registered_on=now,
            next_check=now,
            payload_id=payload.get_id
        )
        metrics_counter('commcare.repeaters.new_record', tags={
            'domain': self.domain,
            'doc_type': self.doc_type
        })
        repeat_record.save()
        repeat_record.attempt_forward_now()
        repeat_record.fire(force_send=True)
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
        # force views to catch up with the change before invalidating the cache
        # for consistency of stale_query
        force_update_repeaters_views()
        # clear cls.by_domain (i.e. filtered by doc type)
        Repeater.by_domain.clear(cls, self.domain)
        Repeater.by_domain.clear(cls, self.domain, stale_query=True)
        # clear Repeater.by_domain (i.e. not filtered by doc type)
        Repeater.by_domain.clear(Repeater, self.domain)
        Repeater.by_domain.clear(Repeater, self.domain, stale_query=True)

    @classmethod
    @quickcache(['cls.__name__', 'domain', 'stale_query'], timeout=60 * 60, memoize_timeout=10)
    def by_domain(cls, domain, stale_query=False):
        key = [domain]
        stale_kwargs = {}
        if stale_query:
            stale_kwargs['stale'] = stale_ok()
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
            wrap_doc=False,
            **stale_kwargs
        )

        return [cls.wrap(repeater_doc['doc']) for repeater_doc in raw_docs
                if cls.get_class_from_doc_type(repeater_doc['doc']['doc_type'])]

    @classmethod
    def wrap(cls, data):
        data.pop('name', None)
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
        # respect the `retry` field of RepeaterResponse
        return getattr(response, 'retry', True)

    def get_headers(self, repeat_record):
        # to be overridden
        return self.generator.get_headers()

    @property
    def plaintext_password(self):

        def clean_repr(bytes_repr):
            """
            Drops the bytestring representation from ``bytes_repr``

            >>> clean_repr("b'spam'")
            'spam'
            """
            if bytes_repr.startswith("b'") and bytes_repr.endswith("'"):
                return bytes_repr[2:-1]
            return bytes_repr

        if self.password is None:
            return ''
        if self.password.startswith('${algo}$'.format(algo=ALGO_AES)):
            ciphertext = self.password.split('$', 2)[2]
            # Work around Py2to3 string-handling bug in encryption code
            # (fixed on 2018-03-12 by commit 3a900068)
            ciphertext = clean_repr(ciphertext)
            return b64_aes_decrypt(ciphertext)
        return self.password

    @property
    def verify(self):
        return not self.skip_cert_verify

    def send_request(self, repeat_record, payload):
        url = self.get_url(repeat_record)
        return simple_post(
            self.domain, url, payload,
            headers=self.get_headers(repeat_record),
            auth_manager=self.connection_settings.get_auth_manager(),
            verify=self.verify,
            notify_addresses=self.connection_settings.notify_addresses,
            payload_id=repeat_record.payload_id,
        )

    def fire_for_record(self, repeat_record):
        payload = self.get_payload(repeat_record)
        try:
            response = self.send_request(repeat_record, payload)
        except (Timeout, ConnectionError) as error:
            log_repeater_timeout_in_datadog(self.domain)
            return self.handle_response(RequestConnectionError(error), repeat_record)
        except RequestException as err:
            return self.handle_response(err, repeat_record)
        except PossibleSSRFAttempt:
            return self.handle_response(Exception("Invalid URL"), repeat_record)
        except Exception as e:
            # This shouldn't ever happen in normal operation and would mean code broke
            # we want to notify ourselves of the error detail and tell the user something vague
            notify_exception(None, "Unexpected error sending repeat record request")
            return self.handle_response(Exception("Internal Server Error"), repeat_record)
        else:
            return self.handle_response(response, repeat_record)

    def handle_response(self, result, repeat_record):
        """
        route the result to the success, failure, or exception handlers

        result may be either a response object or an exception
        """
        if isinstance(result, Exception):
            attempt = repeat_record.handle_exception(result)
        elif is_response(result) and 200 <= result.status_code < 300 or result is True:
            attempt = repeat_record.handle_success(result)
        else:
            attempt = repeat_record.handle_failure(result)
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
            notify_addresses_str=self.notify_addresses_str or '',
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

    def send_request(self, repeat_record, payload):
        """Add custom response handling to allow more nuanced handling of form errors"""
        response = super().send_request(repeat_record, payload)
        return self.get_response(response)

    @staticmethod
    def get_response(response):
        from couchforms.openrosa_response import ResponseNature, parse_openrosa_response
        openrosa_response = parse_openrosa_response(response.text)
        if not openrosa_response:
            # unable to parse response so just let normal handling take place
            return response

        if response.status_code == 422:
            # openrosa v3
            retry = openrosa_response.nature != ResponseNature.PROCESSING_FAILURE
            return RepeaterResponse(422, openrosa_response.nature, openrosa_response.message, retry)

        if response.status_code == 201 and openrosa_response.nature == ResponseNature.SUBMIT_ERROR:
            # openrosa v2
            return RepeaterResponse(422, ResponseNature.SUBMIT_ERROR, openrosa_response.message, False)

        return response


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


class LocationRepeater(Repeater):
    friendly_name = _("Forward Locations")

    payload_generator_classes = (LocationPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        return SQLLocation.objects.get(location_id=repeat_record.payload_id)


def get_all_repeater_types():
    return OrderedDict([
        (to_function(cls, failhard=True).__name__, to_function(cls, failhard=True))
        for cls in settings.REPEATER_CLASSES
    ])


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

    @property
    def created_at(self):
        # Used by .../case/partials/repeat_records.html
        return self.datetime


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
        retry_interval = _get_retry_interval(self.last_checked, now)
        return RepeatRecordAttempt(
            cancelled=False,
            datetime=now,
            failure_reason=failure_reason,
            success_response=None,
            next_check=now + retry_interval,
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
        if not is_response(response):
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
        if is_response(response):
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

    def attempt_forward_now(self, is_retry=False):
        from corehq.motech.repeaters.tasks import process_repeat_record, retry_process_repeat_record

        def is_ready():
            return self.next_check < datetime.utcnow()

        def already_processed():
            return self.succeeded or self.cancelled or self.next_check is None

        if already_processed() or not is_ready():
            return

        # Set the next check to happen an arbitrarily long time from now.
        # This way if there's a delay in calling `process_repeat_record` (which
        # also sets or clears next_check) we won't queue this up in duplicate.
        # If `process_repeat_record` is totally borked, this future date is a
        # fallback.
        self.next_check = datetime.utcnow() + timedelta(hours=48)
        try:
            self.save()
        except ResourceConflict:
            # Another process beat us to the punch. This takes advantage
            # of Couch DB's optimistic locking, which prevents a process
            # with stale data from overwriting the work of another.
            return

        # separated for improved datadog reporting
        if is_retry:
            retry_process_repeat_record.delay(self)
        else:
            process_repeat_record.delay(self)

    def requeue(self):
        self.cancelled = False
        self.succeeded = False
        self.failure_reason = ''
        self.overall_tries = 0
        self.next_check = datetime.utcnow()


class SQLRepeatRecord(models.Model):
    domain = models.CharField(max_length=126)
    couch_id = models.CharField(max_length=36, null=True, blank=True)
    payload_id = models.CharField(max_length=36)
    repeater_stub = models.ForeignKey(RepeaterStub,
                                      on_delete=models.CASCADE,
                                      related_name='repeat_records')
    state = models.TextField(choices=RECORD_STATES,
                             default=RECORD_PENDING_STATE)
    registered_at = models.DateTimeField()

    class Meta:
        db_table = 'repeaters_repeatrecord'
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['couch_id']),
            models.Index(fields=['payload_id']),
            models.Index(fields=['registered_at']),
        ]
        ordering = ['registered_at']

    def requeue(self):
        # Changing "success" to "pending" and "cancelled" to "failed"
        # preserves the value of `self.failure_reason`.
        if self.state == RECORD_SUCCESS_STATE:
            self.state = RECORD_PENDING_STATE
            self.save()
        elif self.state == RECORD_CANCELLED_STATE:
            self.state = RECORD_FAILURE_STATE
            self.save()

    def add_success_attempt(self, response):
        """
        ``response`` can be a Requests response instance, or True if the
        payload did not result in an API call.
        """
        self.repeater_stub.reset_next_attempt()
        self.sqlrepeatrecordattempt_set.create(
            state=RECORD_SUCCESS_STATE,
            message=format_response(response) or '',
        )
        self.state = RECORD_SUCCESS_STATE
        self.save()

    def add_client_failure_attempt(self, message, retry=True):
        """
        Retry when ``self.repeater`` is next processed. The remote
        service is assumed to be in a good state, so do not back off, so
        that this repeat record does not hold up the rest.
        """
        self.repeater_stub.reset_next_attempt()
        self._add_failure_attempt(message, MAX_ATTEMPTS, retry)

    def add_server_failure_attempt(self, message):
        """
        Server and connection failures are retried later with
        exponential backoff.

        .. note::
           ONLY CALL THIS IF RETRYING MUCH LATER STANDS A CHANCE OF
           SUCCEEDING. Exponential backoff will continue for several
           days and will hold up all other payloads.

        """
        self.repeater_stub.set_next_attempt()
        self._add_failure_attempt(message, MAX_BACKOFF_ATTEMPTS)

    def _add_failure_attempt(self, message, max_attempts, retry=True):
        if retry and self.num_attempts < max_attempts:
            state = RECORD_FAILURE_STATE
        else:
            state = RECORD_CANCELLED_STATE
        self.sqlrepeatrecordattempt_set.create(
            state=state,
            message=message,
        )
        self.state = state
        self.save()

    def add_payload_exception_attempt(self, message, tb_str):
        self.sqlrepeatrecordattempt_set.create(
            state=RECORD_CANCELLED_STATE,
            message=message,
            traceback=tb_str,
        )
        self.state = RECORD_CANCELLED_STATE
        self.save()

    @property
    def attempts(self):
        return self.sqlrepeatrecordattempt_set.all()

    @property
    def num_attempts(self):
        # Uses `len(queryset)` instead of `queryset.count()` to use
        # prefetched attempts, if available.
        return len(self.attempts)

    def get_numbered_attempts(self):
        for i, attempt in enumerate(self.attempts, start=1):
            yield i, attempt

    @property
    def record_id(self):
        # Used by Repeater.get_url() ... by SQLRepeatRecordReport._make_row()
        return self.pk

    @property
    def last_checked(self):
        # Used by .../case/partials/repeat_records.html
        return self.repeater.last_attempt_at

    @property
    def url(self):
        # Used by .../case/partials/repeat_records.html
        return self.repeater.couch_repeater.get_url(self)

    @property
    def failure_reason(self):
        if has_failed(self):
            return self.last_message
        else:
            return ''

    @property
    def last_message(self):
        # Uses `list(queryset)[-1]` instead of `queryset.last()` to use
        # prefetched attempts, if available.
        attempts = list(self.attempts)
        return attempts[-1].message if attempts else ''


class SQLRepeatRecordAttempt(models.Model):
    repeat_record = models.ForeignKey(SQLRepeatRecord,
                                      on_delete=models.CASCADE)
    state = models.TextField(choices=RECORD_STATES)
    message = models.TextField(blank=True, default='')
    traceback = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'repeaters_repeatrecordattempt'
        ordering = ['created_at']


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


def attempt_forward_now(repeater_stub: RepeaterStub):
    from corehq.motech.repeaters.tasks import process_repeater_stub

    if not domain_can_forward(repeater_stub.domain):
        return
    if not repeater_stub.is_ready:
        return
    process_repeater_stub.delay(repeater_stub)


def get_payload(repeater: Repeater, repeat_record: SQLRepeatRecord) -> str:
    try:
        return repeater.get_payload(repeat_record)
    except Exception as err:
        log_repeater_error_in_datadog(
            repeater.domain,
            status_code=None,
            repeater_type=repeater.__class__.__name__
        )
        repeat_record.add_payload_exception_attempt(
            message=str(err),
            tb_str=traceback.format_exc()
        )
        raise


def send_request(
    repeater: Repeater,
    repeat_record: SQLRepeatRecord,
    payload: Any,
) -> bool:
    """
    Calls ``repeater.send_request()`` and handles the result.

    Returns True on success or cancelled, which means the caller should
    not retry. False means a retry should be attempted later.
    """

    def is_success(resp):
        return (
            is_response(resp)
            and 200 <= resp.status_code < 300
            # `response` is `True` if the payload did not need to be
            # sent. (This can happen, for example, with DHIS2 if the
            # form that triggered the forwarder doesn't contain data
            # for a DHIS2 Event.)
            or resp is True
        )

    def allow_retries(response):
        # respect the `retry` field of RepeaterResponse
        return getattr(response, 'retry', True)

    def later_might_be_better(resp):
        return is_response(resp) and resp.status_code in (
            502,  # Bad Gateway
            503,  # Service Unavailable
            504,  # Gateway Timeout
        )

    try:
        response = repeater.send_request(repeat_record, payload)
    except (Timeout, ConnectionError) as err:
        log_repeater_timeout_in_datadog(repeat_record.domain)
        message = str(RequestConnectionError(err))
        repeat_record.add_server_failure_attempt(message)
    except Exception as err:
        repeat_record.add_client_failure_attempt(str(err))
    else:
        if is_success(response):
            if is_response(response):
                # Log success in Datadog if the payload was sent.
                log_repeater_success_in_datadog(
                    repeater.domain,
                    response.status_code,
                    repeater_type=repeater.__class__.__name__
                )
            repeat_record.add_success_attempt(response)
        else:
            message = format_response(response)
            if later_might_be_better(response):
                repeat_record.add_server_failure_attempt(message)
            else:
                retry = allow_retries(response)
                repeat_record.add_client_failure_attempt(message, retry)
    return repeat_record.state in (RECORD_SUCCESS_STATE,
                                   RECORD_CANCELLED_STATE)  # Don't retry


def is_queued(record):
    return record.state in (RECORD_PENDING_STATE, RECORD_FAILURE_STATE)


def has_failed(record):
    return record.state in (RECORD_FAILURE_STATE, RECORD_CANCELLED_STATE)


def format_response(response) -> Optional[str]:
    if not is_response(response):
        return None
    response_text = getattr(response, "text", "")
    if response_text:
        return f'{response.status_code}: {response.reason}\n{response_text}'
    return f'{response.status_code}: {response.reason}'


def is_response(duck):
    """
    Returns True if ``duck`` has the attributes of a Requests response
    instance that this module uses, otherwise False.
    """
    return hasattr(duck, 'status_code') and hasattr(duck, 'reason')


@quickcache(['domain'], timeout=5 * 60)
def are_repeat_records_migrated(domain) -> bool:
    """
    Returns True if ``domain`` has SQLRepeatRecords.

    .. note:: Succeeded and cancelled RepeatRecords may not have been
              migrated to SQLRepeatRecords.
    """
    return SQLRepeatRecord.objects.filter(domain=domain).exists()


def domain_can_forward(domain):
    return domain and (
        domain_has_privilege(domain, ZAPIER_INTEGRATION)
        or domain_has_privilege(domain, DATA_FORWARDING)
    )


# import signals
# Do not remove this import, its required for the signals code to run even though not explicitly used in this file
from corehq.motech.repeaters import signals  # pylint: disable=unused-import,F401
