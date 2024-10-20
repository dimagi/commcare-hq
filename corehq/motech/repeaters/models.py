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
import inspect
import json
import traceback
import uuid
from collections import defaultdict
from contextlib import nullcontext
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.db import models, router
from django.db.models.base import Deferred
from django.dispatch import receiver
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from couchdbkit.exceptions import ResourceNotFound
from jsonfield import JSONField
from memoized import memoized
from requests.exceptions import ConnectionError, RequestException, Timeout

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.xml import LEGAL_VERSIONS, V2
from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.utils.logging import notify_error, notify_exception
from dimagi.utils.parsing import json_format_datetime

from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import (
    CaseTransaction,
    CommCareCase,
    XFormInstance,
)
from corehq.motech.const import (
    MAX_REQUEST_LOG_LENGTH,
    ALL_REQUEST_METHODS,
    REQUEST_POST,
)
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.repeaters.apps import REPEATER_CLASS_MAP
from corehq.motech.repeaters.optionvalue import OptionValue
from corehq.motech.requests import simple_request
from corehq.privileges import DATA_FORWARDING, ZAPIER_INTEGRATION
from corehq.sql_db.fields import CharIdField
from corehq.sql_db.util import paginate_query
from corehq.util.metrics import metrics_counter
from corehq.util.models import ForeignObject, foreign_init
from corehq.util.quickcache import quickcache
from corehq.util.urlvalidate.ip_resolver import CannotResolveHost
from corehq.util.urlvalidate.urlvalidate import PossibleSSRFAttempt

from .const import (
    ENDPOINT_TIMER,
    MAX_ATTEMPTS,
    MAX_BACKOFF_ATTEMPTS,
    MAX_RETRY_WAIT,
    MIN_RETRY_WAIT,
    State,
)
from .exceptions import RequestConnectionError, UnknownRepeater
from .repeater_generators import (
    AppStructureGenerator,
    CaseRepeaterJsonPayloadGenerator,
    CaseRepeaterXMLPayloadGenerator,
    DataRegistryCaseUpdatePayloadGenerator,
    DataSourcePayloadGenerator,
    FormRepeaterJsonPayloadGenerator,
    FormRepeaterXMLPayloadGenerator,
    LocationPayloadGenerator,
    ReferCasePayloadGenerator,
    ShortFormRepeaterJsonPayloadGenerator,
    UserPayloadGenerator,
)

# Retry responses with these status codes. All other 4XX status codes
# are treated as InvalidPayload errors.
HTTP_STATUS_4XX_RETRY = (
    HTTPStatus.BAD_REQUEST,
    HTTPStatus.REQUEST_TIMEOUT,
    HTTPStatus.CONFLICT,
    HTTPStatus.PRECONDITION_FAILED,
    HTTPStatus.LOCKED,
    HTTPStatus.FAILED_DEPENDENCY,
    HTTPStatus.TOO_EARLY,
    HTTPStatus.UPGRADE_REQUIRED,
    HTTPStatus.PRECONDITION_REQUIRED,
    HTTPStatus.TOO_MANY_REQUESTS,
)


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


class RepeaterSuperProxy(models.Model):
    # See https://stackoverflow.com/questions/241250/single-table-inheritance-in-django/60894618#60894618
    PROXY_FIELD_NAME = "repeater_type"

    repeater_type = models.CharField(max_length=64, blank=True)

    class Meta:
        abstract = True

    def clear_caches(self):
        """Override this to clear any cache that the repeater type might be using"""
        pass

    def save(self, *args, **kwargs):
        self.clear_caches()
        self.repeater_type = self._repeater_type
        self.name = self.name or self.connection_settings.name
        if 'update_fields' in kwargs:
            kwargs['update_fields'].extend(['repeater_type', 'name'])
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.clear_caches()
        return super().delete(*args, **kwargs)

    def __new__(cls, *args, **kwargs):
        repeater_class = cls
        # get proxy name, either from kwargs or from args
        proxy_class_name = kwargs.get(cls.PROXY_FIELD_NAME)
        if proxy_class_name is None:
            proxy_name_field_index = cls._meta.fields.index(
                cls._meta.get_field(cls.PROXY_FIELD_NAME))
            try:
                proxy_class_name = args[proxy_name_field_index]
                if isinstance(proxy_class_name, Deferred):
                    return super().__new__(repeater_class)
            except IndexError:
                pass
            else:
                repeater_class = REPEATER_CLASS_MAP.get(proxy_class_name)
                if repeater_class is None:
                    details = {
                        'args': args,
                        'kwargs': kwargs
                    }
                    notify_error(UnknownRepeater(proxy_class_name), details=details)
                    # Fallback to creating Repeater if repeater class is not found
                    repeater_class = cls

        return super().__new__(repeater_class)


class RepeaterManager(models.Manager):

    def all_ready(self):
        """
        Return all Repeaters ready to be forwarded.
        """
        not_paused = models.Q(is_paused=False)
        next_attempt_not_in_the_future = (
            models.Q(next_attempt_at__isnull=True)
            | models.Q(next_attempt_at__lte=timezone.now())
        )
        repeat_records_ready_to_send = models.Q(
            repeat_records__state__in=(State.Pending, State.Fail)
        )
        return (
            self.get_queryset()
            .filter(not_paused)
            .filter(next_attempt_not_in_the_future)
            .filter(repeat_records_ready_to_send)
        )

    def get_all_ready_ids_by_domain(self):
        results = defaultdict(list)
        query = self.all_ready().values_list('domain', 'id')
        for (domain, id_uuid) in query.all():
            results[domain].append(id_uuid.hex)
        return results

    def get_queryset(self):
        repeater_obj = self.model()
        if type(repeater_obj).__name__ == "Repeater":
            return super().get_queryset().filter(is_deleted=False)
        else:
            return super().get_queryset().filter(repeater_type=repeater_obj._repeater_type, is_deleted=False)

    def by_domain(self, domain):
        return list(self.filter(domain=domain))


@foreign_init
class Repeater(RepeaterSuperProxy):
    id = models.UUIDField(primary_key=True, db_column="id_", default=uuid.uuid4)
    domain = CharIdField(max_length=126, db_index=True)
    name = models.CharField(max_length=255, null=True)
    format = models.CharField(max_length=64, null=True)
    request_method = models.CharField(
        choices=list(zip(ALL_REQUEST_METHODS, ALL_REQUEST_METHODS)),
        default=REQUEST_POST,
        max_length=16,
    )
    is_paused = models.BooleanField(default=False)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    max_workers = models.IntegerField(default=0)
    options = JSONField(default=dict)
    connection_settings_id = models.IntegerField(db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    last_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)

    objects = RepeaterManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'repeaters_repeater'
        indexes = [
            models.Index(
                fields=['next_attempt_at'],
                condition=models.Q(("is_deleted", False), ("is_paused", False)),
                name='next_attempt_at_partial_idx',
            ),
        ]

    payload_generator_classes = ()

    friendly_name = _("Data")

    _has_config = False

    def __str__(self):
        return self.name or self.connection_settings.name

    def _get_connection_settings(self, id_):
        return ConnectionSettings.objects.get(id=id_, domain=self.domain)

    connection_settings = ForeignObject(connection_settings_id, _get_connection_settings)

    @property
    def repeater_id(self):
        return self.id.hex

    @cached_property
    def _optionvalue_fields(self):
        return [
            attr_tuple[0]
            for attr_tuple in inspect.getmembers(self.__class__)
            if isinstance(attr_tuple[1], OptionValue)
        ]

    def to_json(self):
        repeater_dict = self.__dict__.copy()
        options = repeater_dict.pop('options', None)

        # Populating OptionValue attrs
        for attr in self._optionvalue_fields:
            if attr == 'include_app_id_param':
                continue
            repeater_dict[attr] = (options.get(attr)
                if attr in options
                else getattr(self.__class__, attr).get_default_value())

        # include_app_id_param is a constant in some Repeaters and will not come up in options
        if hasattr(self, 'include_app_id_param'):
            repeater_dict['include_app_id_param'] = self.include_app_id_param

        # Remove keys which were not present in couch
        repeater_dict.pop('_state', None)
        repeater_dict.pop('id', None)
        repeater_dict.pop('is_deleted', None)
        repeater_dict.pop('next_attempt_at', None)
        repeater_dict.pop('last_attempt_at', None)
        repeater_dict.pop('_ForeignObject_connection_settings', None)

        self._convert_to_serializable(repeater_dict)
        return repeater_dict

    def _convert_to_serializable(self, repeater_dict):
        for key, val in repeater_dict.items():
            try:
                json.dumps(val)
            except Exception as e:
                if isinstance(val, datetime):
                    repeater_dict[key] = json_format_datetime(val)
                    continue
                notify_exception(
                    None,
                    f"""Unable to serialize {key} for repeater_id {self.repeater_id}.
                    You may implement to_json for {self.repeater_type}"""
                )
                raise e

    def get_url(self, record):
        return self.connection_settings.url

    @classmethod
    @property
    def _repeater_type(cls):
        return cls.__name__

    @property
    def repeat_records_ready(self):
        """
        A QuerySet of repeat records in the Pending or Fail state in the
        order in which they were registered
        """
        return (
            self.repeat_records
            .filter(state__in=(State.Pending, State.Fail))
            .order_by('registered_at')
        )

    @property
    def num_workers(self):
        # If num_workers is 1, repeat records are sent in the order in
        # which they were registered.
        num_workers = self.max_workers or settings.DEFAULT_REPEATER_WORKERS
        return min(num_workers, settings.MAX_REPEATER_WORKERS)

    def set_backoff(self):
        now = datetime.utcnow()
        interval = _get_retry_interval(self.last_attempt_at, now)
        self.last_attempt_at = now
        self.next_attempt_at = now + interval
        # Save using QuerySet.update() to avoid a possible race condition
        # with self.pause(), etc. and to skip the unnecessary functionality
        # in RepeaterSuperProxy.save().
        Repeater.objects.filter(id=self.repeater_id).update(
            last_attempt_at=now,
            next_attempt_at=now + interval,
        )

    def reset_backoff(self):
        if self.last_attempt_at or self.next_attempt_at:
            # `_get_retry_interval()` implements exponential backoff by
            # multiplying the previous interval by 3. Set last_attempt_at
            # to None so that the next time we need to back off, we
            # know it is the first interval.
            self.last_attempt_at = None
            self.next_attempt_at = None
            # Avoid a possible race condition with self.pause(), etc.
            Repeater.objects.filter(id=self.repeater_id).update(
                last_attempt_at=None,
                next_attempt_at=None,
            )

    @property
    def verify(self):
        return not self.connection_settings.skip_cert_verify

    def register(self, payload, fire_synchronously=False):
        if not self.allowed_to_forward(payload):
            return
        now = datetime.utcnow()
        repeat_record = RepeatRecord(
            repeater_id=self.id,
            domain=self.domain,
            registered_at=now,
            next_check=now,
            payload_id=payload.get_id
        )
        repeat_record.save()

        if fire_synchronously:
            # Prime the cache to prevent unnecessary lookup. Only do this for synchronous repeaters
            # to prevent serializing the repeater in the celery task payload
            repeat_record.__dict__["repeater"] = self
        repeat_record.attempt_forward_now(fire_synchronously=fire_synchronously)
        return repeat_record

    def allowed_to_forward(self, payload):
        """
        Return True/False depending on whether the payload meets forwarding criteria or not
        """
        return True

    def pause(self):
        self.is_paused = True
        Repeater.objects.filter(id=self.repeater_id).update(is_paused=True)

    def resume(self):
        self.is_paused = False
        Repeater.objects.filter(id=self.repeater_id).update(is_paused=False)

    def retire(self):
        self.is_deleted = True
        Repeater.objects.filter(id=self.repeater_id).update(is_deleted=True)

    def _time_request(self, repeat_record, payload, timing_context):
        with timing_context(ENDPOINT_TIMER) if timing_context else nullcontext():
            return self.send_request(repeat_record, payload)

    def fire_for_record(self, repeat_record, timing_context=None):
        payload = self.get_payload(repeat_record)
        try:
            response = self._time_request(repeat_record, payload, timing_context)
        except (Timeout, ConnectionError) as error:
            self.handle_response(RequestConnectionError(error), repeat_record)
        except RequestException as err:
            self.handle_response(err, repeat_record)
        except (PossibleSSRFAttempt, CannotResolveHost):
            self.handle_response(Exception("Invalid URL"), repeat_record)
        except Exception:
            # This shouldn't ever happen in normal operation and would mean code broke
            # we want to notify ourselves of the error detail and tell the user something vague
            notify_exception(None, "Unexpected error sending repeat record request")
            self.handle_response(Exception("Internal Server Error"), repeat_record)
        else:
            self.handle_response(response, repeat_record)

    @memoized
    def get_payload(self, repeat_record):
        return self.generator.get_payload(repeat_record, self.payload_doc(repeat_record))

    def send_request(self, repeat_record, payload):
        url = self.get_url(repeat_record)
        return simple_request(
            self.domain, url, payload,
            headers=self.get_headers(repeat_record),
            auth_manager=self.connection_settings.get_auth_manager(),
            verify=not self.connection_settings.skip_cert_verify,
            notify_addresses=self.connection_settings.notify_addresses,
            payload_id=repeat_record.payload_id,
            method=self.request_method,
        )

    def handle_response(self, result, repeat_record):
        """
        route the result to the success, failure, timeout, or exception handlers

        result may be either a response object or an exception
        """
        if isinstance(result, RequestConnectionError):
            repeat_record.handle_timeout(result)
        elif isinstance(result, Exception):
            repeat_record.handle_exception(result)
        elif is_success_response(result):
            repeat_record.handle_success(result)
        elif not is_response(result) or (
            500 <= result.status_code < 600
            or result.status_code in HTTP_STATUS_4XX_RETRY
        ):
            repeat_record.handle_failure(result)
        else:
            message = format_response(result)
            repeat_record.handle_payload_error(message)

    def get_headers(self, repeat_record):
        # to be overridden
        return self.generator.get_headers()

    @property
    @memoized
    def generator(self):
        return self._get_payload_generator(self._format_or_default_format())

    def _get_payload_generator(self, payload_format):
        from corehq.motech.repeaters.repeater_generators import (
            RegisterGenerator,
        )
        gen = RegisterGenerator.generator_class_by_repeater_format(
            self.__class__,
            payload_format
        )
        return gen(self)

    def _format_or_default_format(self):
        from corehq.motech.repeaters.repeater_generators import (
            RegisterGenerator,
        )
        return self.format or RegisterGenerator.default_format_by_repeater(self.__class__)

    def payload_doc(self, repeat_record):
        raise NotImplementedError

    def allow_retries(self, response):
        """Whether to requeue the repeater when it fails
        """
        # respect the `retry` field of RepeaterResponse
        return getattr(response, 'retry', True)

    @classmethod
    def available_for_domain(cls, domain):
        """Returns whether this repeater can be used by a particular domain
        """
        return True

    @property
    def form_class_name(self):
        """
        Return the name of the class whose edit form this class uses.

        (Most classes that extend CaseRepeater, and all classes that
        extend FormRepeater, use the same form.)
        """
        return self._repeater_type


class FormRepeater(Repeater):

    include_app_id_param = OptionValue(default=True)
    white_listed_form_xmlns = OptionValue(default=list)
    user_blocklist = OptionValue(default=list)

    class Meta:
        proxy = True

    friendly_name = _("Forward Forms")

    payload_generator_classes = (FormRepeaterXMLPayloadGenerator, FormRepeaterJsonPayloadGenerator)

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(repeat_record.payload_id, repeat_record.domain)

    @property
    def form_class_name(self):
        """
        FormRepeater and its subclasses use the same form for editing
        """
        return 'FormRepeater'

    def allowed_to_forward(self, payload):
        return (
            payload.xmlns != DEVICE_LOG_XMLNS
            and (
                not self.white_listed_form_xmlns
                or payload.xmlns in self.white_listed_form_xmlns
            )
        )

    def get_url(self, repeat_record):
        url = super().get_url(repeat_record)
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
        headers = super().get_headers(repeat_record)
        headers.update({
            "received-on": json_format_datetime(self.payload_doc(repeat_record).received_on)
        })
        return headers


class CaseRepeater(Repeater):
    """
    Record that cases should be repeated to a new url

    """
    version = OptionValue(choices=LEGAL_VERSIONS, default=V2)
    white_listed_case_types = OptionValue(default=list)
    black_listed_users = OptionValue(default=list)

    class Meta:
        proxy = True

    friendly_name = _("Forward Cases")

    payload_generator_classes = (CaseRepeaterXMLPayloadGenerator, CaseRepeaterJsonPayloadGenerator)

    @property
    def form_class_name(self):
        """
        CaseRepeater and most of its subclasses use the same form for editing
        """
        return 'CaseRepeater'

    def allowed_to_forward(self, payload):
        return self._allowed_case_type(payload) and self._allowed_user(payload)

    def _allowed_case_type(self, payload):
        return not self.white_listed_case_types or payload.type in self.white_listed_case_types

    def _allowed_user(self, payload):
        return not self.black_listed_users or self.payload_user_id(payload) not in self.black_listed_users

    def payload_user_id(self, payload):
        # get the user_id who submitted the payload, note, it's not the owner_id
        return payload.actions[-1].user_id

    @memoized
    def payload_doc(self, repeat_record):
        return CommCareCase.objects.get_case(repeat_record.payload_id, repeat_record.domain)

    def get_headers(self, repeat_record):
        headers = super().get_headers(repeat_record)
        headers.update({
            "server-modified-on": json_format_datetime(self.payload_doc(repeat_record).server_modified_on)
        })
        return headers


class CreateCaseRepeater(CaseRepeater):
    class Meta:
        proxy = True

    friendly_name = _("Forward Cases on Creation Only")

    def allowed_to_forward(self, payload):
        # assume if there's exactly 1 xform_id that modified the case it's being created
        return super().allowed_to_forward(payload) and len(payload.xform_ids) == 1


class UpdateCaseRepeater(CaseRepeater):
    """
    Just like CaseRepeater but only create records if the case is being updated.
    Used by the Zapier integration.
    """
    class Meta:
        proxy = True

    friendly_name = _("Forward Cases on Update Only")

    def allowed_to_forward(self, payload):
        return super().allowed_to_forward(payload) and len(payload.xform_ids) > 1


class ReferCaseRepeater(CreateCaseRepeater):
    """
    A repeater that triggers off case creation but sends a form creating cases in
    another commcare project
    """
    class Meta:
        proxy = True

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
        return get_repeater_response_from_submission_response(
            super().send_request(repeat_record, payload)
        )


class DataRegistryCaseUpdateRepeater(CreateCaseRepeater):
    """
    A repeater that triggers off case creation but sends a form to update cases in
    another commcare project space.
    """
    class Meta:
        proxy = True

    friendly_name = _("Update Cases in another CommCare Project via a Data Registry")
    payload_generator_classes = (DataRegistryCaseUpdatePayloadGenerator,)

    def form_class_name(self):
        return 'DataRegistryCaseUpdateRepeater'

    @classmethod
    def available_for_domain(cls, domain):
        return toggles.DATA_REGISTRY_CASE_UPDATE_REPEATER.enabled(domain)

    def get_url(self, repeat_record):
        new_domain = self.payload_doc(repeat_record).get_case_property('target_domain')
        return self.connection_settings.url.format(domain=new_domain)

    def send_request(self, repeat_record, payload):
        return get_repeater_response_from_submission_response(
            super().send_request(repeat_record, payload)
        )

    def allowed_to_forward(self, payload):
        if not super().allowed_to_forward(payload):
            return False

        # Exclude extension cases where the host is also a case type that this repeater
        # would act on since they get forwarded along with their host
        host_indices = payload.get_indices(relationship=CASE_INDEX_EXTENSION)
        for host_index in host_indices:
            if host_index.referenced_type in self.white_listed_case_types:
                return False

        transaction = CaseTransaction.objects.get_most_recent_form_transaction(payload.case_id)
        if transaction:
            # prevent chaining updates
            return transaction.xmlns != DataRegistryCaseUpdatePayloadGenerator.XMLNS

        return True


class ShortFormRepeater(Repeater):
    """
    Record that form id & case ids should be repeated to a new url

    """
    version = OptionValue(choices=LEGAL_VERSIONS, default=V2)

    class Meta:
        proxy = True

    friendly_name = _("Forward Form Stubs")

    payload_generator_classes = (ShortFormRepeaterJsonPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        return XFormInstance.objects.get_form(repeat_record.payload_id, repeat_record.domain)

    def allowed_to_forward(self, payload):
        return payload.xmlns != DEVICE_LOG_XMLNS

    def get_headers(self, repeat_record):
        headers = super().get_headers(repeat_record)
        headers.update({
            "received-on": json_format_datetime(self.payload_doc(repeat_record).received_on)
        })
        return headers


class AppStructureRepeater(Repeater):

    class Meta:
        proxy = True

    friendly_name = _("Forward App Schema Changes")

    payload_generator_classes = (AppStructureGenerator,)

    def payload_doc(self, repeat_record):
        return None


class UserRepeater(Repeater):

    class Meta:
        proxy = True

    friendly_name = _("Forward Users")

    payload_generator_classes = (UserPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        return CommCareUser.get(repeat_record.payload_id)


class LocationRepeater(Repeater):

    class Meta:
        proxy = True

    friendly_name = _("Forward Locations")

    payload_generator_classes = (LocationPayloadGenerator,)

    @memoized
    def payload_doc(self, repeat_record):
        return SQLLocation.objects.get(location_id=repeat_record.payload_id)


def get_repeater_response_from_submission_response(response):
    from couchforms.openrosa_response import (
        ResponseNature,
        parse_openrosa_response,
    )
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


def get_all_repeater_types():
    return dict(REPEATER_CLASS_MAP)


class DataSourceRepeater(Repeater):
    """
    Forwards the UCR data source rows that are updated by a form
    submission or a case creation/update.

    A ``DataSourceRepeater`` is responsible for a single data source.
    """
    class Meta:
        proxy = True

    data_source_id = OptionValue(default=None)

    friendly_name = _("Forward Data Source Data")

    payload_generator_classes = (DataSourcePayloadGenerator,)

    def allowed_to_forward(
        self,
        payload,  # type DataSourceUpdateLog
    ):
        return payload.data_source_id == self.data_source_id

    def payload_doc(self, repeat_record):
        from corehq.apps.userreports.models import get_datasource_config
        from corehq.apps.userreports.util import (
            DataSourceUpdateLog,
            get_indicator_adapter,
        )

        config, _ = get_datasource_config(
            config_id=self.data_source_id,
            domain=self.domain
        )
        datasource_adapter = get_indicator_adapter(config, load_source='repeat_record')
        rows = datasource_adapter.get_rows_by_doc_id(repeat_record.payload_id)
        return DataSourceUpdateLog(
            domain=self.domain,
            data_source_id=self.data_source_id,
            doc_id=repeat_record.payload_id,
            rows=rows,
        )

    def clear_caches(self):
        DataSourceRepeater.datasource_is_subscribed_to.clear(self.domain, self.data_source_id)

    @staticmethod
    @quickcache(['domain', 'data_source_id'], timeout=15 * 60)
    def datasource_is_subscribed_to(domain, data_source_id):
        # Since Repeater.options is not a native django JSON field, we cannot query it like a django json field
        return DataSourceRepeater.objects.filter(
            domain=domain, options={"data_source_id": data_source_id}
        ).exists()


# on_delete=DB_CASCADE denotes ON DELETE CASCADE in the database. The
# constraints are configured in a migration. Note that Django signals
# will not fire on records deleted via cascade.
DB_CASCADE = models.DO_NOTHING


class RepeatRecordManager(models.Manager):

    def count_by_repeater_and_state(self, domain):
        """Returns a dict of dicts {<repeater_id>: {<state>: <count>, ...}, ...}

        The returned dicts are defaultdicts to allow lookups without
        concern for missing keys. Counts default to zero.
        """
        result = defaultdict(lambda: defaultdict(int))
        query = (
            self.filter(domain=domain)
            .values('repeater_id', 'state')
            .order_by()
            .annotate(count=models.Count('*'))
            .values_list('repeater_id', 'state', 'count')
        )
        for repeater_id, state, count in query:
            result[repeater_id][state] = count
        return result

    def count_overdue(self, threshold=timedelta(minutes=10)):
        return self.filter(
            next_check__isnull=False,
            next_check__lt=datetime.utcnow() - threshold
        ).count()

    def iterate(self, domain, repeater_id=None, state=None, chunk_size=1000):
        db = router.db_for_read(self.model)
        where = models.Q(domain=domain)
        if repeater_id:
            where &= models.Q(repeater__id=repeater_id)
        if state is not None:
            where &= models.Q(state=state)
        return paginate_query(db, self.model, where, query_size=chunk_size)

    def page(self, domain, skip, limit, repeater_id=None, state=None):
        """Get a page of repeat records

        WARNING this is inefficient for large skip values.
        """
        queryset = self.filter(domain=domain)
        if repeater_id:
            queryset = queryset.filter(repeater__id=repeater_id)
        if state is not None:
            queryset = queryset.filter(state=state)
        return (queryset.order_by('-registered_at')[skip:skip + limit]
                .select_related('repeater')
                .prefetch_related('attempt_set'))

    def iter_partition(self, start, partition, total_partitions):
        from django.db.models import F
        query = self.annotate(partition_id=F("id") % total_partitions).filter(
            partition_id=partition,
            next_check__isnull=False,
            next_check__lt=start,
        ).order_by("next_check", "id")
        offset = {}
        while True:
            result = list(query.filter(**offset)[:1000])
            yield from result
            if len(result) < 1000:
                break
            offset = {
                "next_check__gte": result[-1].next_check,
                "id__gt": result[-1].id,
            }

    def get_domains_with_records(self):
        return self.order_by().values_list("domain", flat=True).distinct()

    def get_repeat_record_ids(self, domain, repeater_id=None, state=None, payload_id=None):
        where = models.Q(domain=domain)
        if repeater_id:
            where &= models.Q(repeater__id=repeater_id)
        if state:
            where &= models.Q(state=state)
        if payload_id:
            where &= models.Q(payload_id=payload_id)

        return list(self.filter(where).order_by().values_list("id", flat=True))


class RepeatRecord(models.Model):
    domain = models.CharField(max_length=126)
    payload_id = models.CharField(max_length=255)
    repeater = models.ForeignKey(
        Repeater,
        on_delete=DB_CASCADE,
        db_column="repeater_id_",
        related_name='repeat_records',
    )
    state = models.PositiveSmallIntegerField(
        choices=State.choices,
        default=State.Pending,
        db_index=True,
    )
    registered_at = models.DateTimeField()
    next_check = models.DateTimeField(null=True, default=None)
    max_possible_tries = models.IntegerField(default=MAX_BACKOFF_ATTEMPTS)

    objects = RepeatRecordManager()

    class Meta:
        indexes = [
            models.Index(fields=['domain', 'registered_at']),
            models.Index(fields=['payload_id']),
            models.Index(
                name="next_check_not_null",
                fields=["next_check"],
                condition=models.Q(next_check__isnull=False),
            )
        ]
        constraints = [
            models.CheckConstraint(
                name="next_check_pending_or_null",
                check=(
                    models.Q(next_check__isnull=True)
                    | models.Q(next_check__isnull=False, state=State.Pending)
                    | models.Q(next_check__isnull=False, state=State.Fail)
                )
            ),
        ]
        ordering = ['registered_at']

    def requeue(self):
        # Changing "success" to "pending" and "cancelled" to "failed"
        # preserves the value of `self.failure_reason`.
        if self.succeeded:
            self.state = State.Pending
        elif self.state in (State.Cancelled, State.InvalidPayload):
            self.state = State.Fail
        self.next_check = datetime.utcnow()
        self.max_possible_tries = self.num_attempts + MAX_BACKOFF_ATTEMPTS
        self.save()

    def add_success_attempt(self, response):
        """
        ``response`` can be a Requests response instance, or True if the
        payload did not result in an API call.
        """
        # NOTE a 204 status here could mean either
        # 1. the request was not sent, in which case response is
        #    probably RepeaterResponse(204, "No Content")
        # 2. the request was sent, and the remote end responded
        #    with 204 (No Content)
        # Interpreting 204 as Empty (request not sent) is wrong,
        # although the Couch RepeatRecord did the same.
        code = getattr(response, "status_code", None)
        state = State.Empty if code == 204 else State.Success
        self.attempt_set.create(state=state, message=format_response(response) or '')
        self.state = state
        self.next_check = None
        self.save()

    def add_client_failure_attempt(self, message, retry=True):
        """
        Retry when ``self.repeater`` is next processed. The remote
        service is assumed to be in a good state, so do not back off, so
        that this repeat record does not hold up the rest.
        """
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
        self._add_failure_attempt(message, MAX_BACKOFF_ATTEMPTS)

    def _add_failure_attempt(self, message, max_attempts, retry=True):
        if retry and self.num_attempts < max_attempts:
            state = State.Fail
            wait = _get_retry_interval(self.last_checked, datetime.utcnow())
        else:
            state = State.Cancelled
        attempt = self.attempt_set.create(state=state, message=message)
        self.state = state
        self.next_check = (attempt.created_at + wait) if state == State.Fail else None
        self.save()

    def add_payload_error_attempt(self, message, traceback_str):
        self.attempt_set.create(
            state=State.InvalidPayload,
            message=message,
            traceback=traceback_str,
        )
        self.state = State.InvalidPayload
        self.next_check = None
        self.save()

    @property
    def attempts(self):
        try:
            attempts = self._prefetched_objects_cache['attempt_set']
        except (AttributeError, KeyError):
            self.__dict__.setdefault("_prefetched_objects_cache", {})
            attempts = self._prefetched_objects_cache['attempt_set'] = self.attempt_set.all()
        return attempts

    @property
    def num_attempts(self):
        # Uses `len(queryset)` instead of `queryset.count()` to use
        # prefetched attempts, if available.
        return len(self.attempts)

    def get_numbered_attempts(self):
        for i, attempt in enumerate(self.attempts, start=1):
            yield i, attempt

    @property
    def last_checked(self):
        # Used by .../case/partials/repeat_records.html
        try:
            return max(a.created_at for a in self.attempts)
        except ValueError:
            return None

    @property
    def url(self):
        # Used by .../case/partials/repeat_records.html
        return self.repeater.get_url(self)

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

    @property
    def succeeded(self):
        """True if the record was sent successfully or if there was nothing to send

        It is considered a successful attempt if the payload was empty
        and nothing was sent, in which case the record will have an
        Empty state.
        """
        # See also the comment in add_success_attempt about possible
        # incorrect status code interpretation resulting in Empty state.
        return self.state == State.Success or self.state == State.Empty

    def is_queued(self):
        return self.state == State.Pending or self.state == State.Fail

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Members below this line have been added to support the
    # Couch repeater processing logic.

    @property
    def exceeded_max_retries(self):
        return self.state == State.Fail and self.num_attempts >= self.max_possible_tries

    @property
    def repeater_type(self):
        return self.repeater.repeater_type

    def fire(self, force_send=False, timing_context=None):
        if force_send or not self.succeeded:
            try:
                self.repeater.fire_for_record(self, timing_context=timing_context)
            except Exception as e:
                self.handle_payload_error(str(e), traceback_str=traceback.format_exc())
            return self.state
        return None

    def attempt_forward_now(self, *, is_retry=False, fire_synchronously=False):
        from corehq.motech.repeaters.tasks import (
            process_repeat_record,
            process_datasource_repeat_record,
            retry_process_repeat_record,
            retry_process_datasource_repeat_record,
        )

        def is_new_synchronous_case_repeater_record():
            """
            Repeat record is a new record for a synchronous case repeater
            See corehq.motech.repeaters.signals.fire_synchronous_case_repeaters
            """
            return fire_synchronously and self.state == State.Pending

        if (
            toggles.PROCESS_REPEATERS.enabled(self.domain, toggles.NAMESPACE_DOMAIN)
            and not is_new_synchronous_case_repeater_record()
        ):
            return

        if self.next_check is None or self.next_check > datetime.utcnow():
            return

        # Set the next check to happen an arbitrarily long time from now.
        # This way if there's a delay in calling `process_repeat_record` (which
        # also sets or clears next_check) we won't queue this up in duplicate.
        # If `process_repeat_record` is totally borked, this future date is a
        # fallback.
        updated = type(self).objects.filter(
            id=self.id,
            next_check=self.next_check
        ).update(next_check=datetime.utcnow() + timedelta(hours=48))
        if not updated:
            # Use optimistic locking to prevent a process with stale
            # data from overwriting the work of another.
            return

        if self.repeater_type in ['DataSourceRepeater']:
            # separated for improved datadog reporting
            task = retry_process_datasource_repeat_record if is_retry else process_datasource_repeat_record
        else:
            # separated for improved datadog reporting
            task = retry_process_repeat_record if is_retry else process_repeat_record
        if fire_synchronously:
            task(self.id, self.domain)
        else:
            task.delay(self.id, self.domain)

    def handle_success(self, response):
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
        self.add_success_attempt(response)

    def handle_failure(self, response):
        log_repeater_error_in_datadog(self.domain, response.status_code, self.repeater_type)
        self.add_server_failure_attempt(format_response(response))

    def handle_exception(self, exception):
        log_repeater_error_in_datadog(self.domain, None, self.repeater_type)
        self.add_client_failure_attempt(str(exception))

    def handle_timeout(self, exception):
        log_repeater_timeout_in_datadog(self.domain)
        self.add_server_failure_attempt(str(exception))

    def handle_payload_error(self, message, traceback_str=''):
        log_repeater_error_in_datadog(self.domain, status_code=None, repeater_type=self.repeater_type)
        self.add_payload_error_attempt(message, traceback_str)

    def cancel(self):
        self.state = State.Cancelled
        self.next_check = None

    def get_payload(self):
        return self.repeater.get_payload(self)

    def postpone_by(self, duration):
        self.next_check = datetime.utcnow() + duration
        self.save()


class RepeatRecordAttempt(models.Model):
    repeat_record = models.ForeignKey(
        RepeatRecord, on_delete=DB_CASCADE, related_name="attempt_set")
    state = models.PositiveSmallIntegerField(choices=State.choices)
    message = models.TextField(blank=True, default='')
    traceback = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']


@receiver(models.signals.pre_save, sender=RepeatRecordAttempt)
def _register_new_attempt_to_clear_cache(sender, instance, **kwargs):
    record = instance._meta.get_field("repeat_record").get_cached_value(instance, None)
    if instance._state.adding and record is not None:
        instance._record_with_new_attempt = record


@receiver(models.signals.post_save, sender=RepeatRecordAttempt)
def _clear_attempts_cache_after_save_new_attempt(sender, instance, **kwargs):
    # Clear cache in post_save because it may get populated by save
    # logic before the save is complete. The post_save signal by itself
    # is insufficient because it cannot identify a new attempt (by the
    # time post_save is called, instance._state.adding is false).
    record = instance.__dict__.pop("_record_with_new_attempt", None)
    if record is not None:
        record.attempt_set._remove_prefetched_objects()


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


def has_failed(record):
    return record.state in (State.Fail, State.Cancelled, State.InvalidPayload)


def format_response(response):
    if not is_response(response):
        return ''
    response_text = getattr(response, "text", "")[:MAX_REQUEST_LOG_LENGTH]
    if response_text:
        return f'{response.status_code}: {response.reason}\n{response_text}'
    return f'{response.status_code}: {response.reason}'


def is_success_response(response):
    return (
        is_response(response)
        and 200 <= response.status_code < 300
        # `response` is `True` if the payload did not need to be sent.
        # (This can happen, for example, if a form submission is
        # transformed into a payload, but the form didn't contain any
        # relevant data and so the payload is empty.)
        or response is True
    )


def is_response(duck):
    """
    Returns True if ``duck`` has the attributes of a Requests response
    instance that this module uses, otherwise False.
    """
    return hasattr(duck, 'status_code') and hasattr(duck, 'reason')


def domain_can_forward(domain):
    """
    Returns whether ``domain`` has data forwarding or Zapier integration
    privileges.

    Used for determining whether to register a repeat record.
    """
    return domain and (
        domain_has_privilege(domain, ZAPIER_INTEGRATION)
        or domain_has_privilege(domain, DATA_FORWARDING)
    )


def domain_can_forward_now(domain):
    """
    Returns ``True`` if ``domain`` has the requisite privileges and data
    forwarding is not paused.

    Used for determining whether to send a repeat record now.
    """
    return (
        domain_can_forward(domain)
        and not toggles.PAUSE_DATA_FORWARDING.enabled(domain)
    )
