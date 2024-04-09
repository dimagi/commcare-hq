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
import warnings
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.db import models, router
from django.db.models.base import Deferred
from django.dispatch import receiver
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from jsonfield import JSONField
from memoized import memoized
from requests.exceptions import ConnectionError, RequestException, Timeout

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.xml import LEGAL_VERSIONS, V2
from couchforms.const import DEVICE_LOG_XMLNS
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateTimeProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    ListProperty,
    StringProperty,
)
from dimagi.utils.couch.migration import SubModelSpec, SyncCouchToSQLMixin, SyncSQLToCouchMixin
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
    REQUEST_METHODS,
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
    MAX_ATTEMPTS,
    MAX_BACKOFF_ATTEMPTS,
    MAX_RETRY_WAIT,
    MIN_RETRY_WAIT,
    RECORD_CANCELLED_STATE,
    RECORD_EMPTY_STATE,
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
    RECORD_SUCCESS_STATE,
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
        return (self.get_queryset()
                .filter(not_paused)
                .filter(next_attempt_not_in_the_future)
                .filter(repeat_records_ready_to_send))

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
        choices=list(zip(REQUEST_METHODS, REQUEST_METHODS)),
        default=REQUEST_POST,
        max_length=16,
    )
    is_paused = models.BooleanField(default=False)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    options = JSONField(default=dict)
    connection_settings_id = models.IntegerField(db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    last_modified = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)

    objects = RepeaterManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'repeaters_repeater'

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
        return self.repeat_records.filter(state__in=(State.Pending, State.Fail))

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

    def get_attempt_info(self, repeat_record):
        return None

    @property
    def verify(self):
        return not self.connection_settings.skip_cert_verify

    def register(self, payload, fire_synchronously=False):
        if not self.allowed_to_forward(payload):
            return
        now = datetime.utcnow()
        repeat_record = SQLRepeatRecord(
            repeater_id=self.id,
            domain=self.domain,
            registered_at=now,
            next_check=now,
            payload_id=payload.get_id
        )
        metrics_counter('commcare.repeaters.new_record', tags={
            'domain': self.domain,
            'doc_type': self.repeater_type,
            'mode': 'sync' if fire_synchronously else 'async'
        })
        repeat_record.save()

        if fire_synchronously:
            # Prime the cache to prevent unnecessary lookup. Only do this for synchronous repeaters
            # to prevent serializing the repeater in the celery task payload
            repeat_record.__dict__["repeater"] = self
        repeat_record.attempt_forward_now(fire_synchronously=fire_synchronously)
        return repeat_record

    def allowed_to_forward(self, payload):
        """
        Return True/False depending on whether the payload meets forawrding criteria or not
        """
        return True

    def pause(self):
        self.is_paused = True
        self.save()

    def resume(self):
        self.is_paused = False
        self.save()

    def retire(self):
        self.is_deleted = True
        self.save()

    def fire_for_record(self, repeat_record):
        payload = self.get_payload(repeat_record)
        try:
            response = self.send_request(repeat_record, payload)
        except (Timeout, ConnectionError) as error:
            log_repeater_timeout_in_datadog(self.domain)
            return self.handle_response(RequestConnectionError(error), repeat_record)
        except RequestException as err:
            return self.handle_response(err, repeat_record)
        except (PossibleSSRFAttempt, CannotResolveHost):
            return self.handle_response(Exception("Invalid URL"), repeat_record)
        except Exception:
            # This shouldn't ever happen in normal operation and would mean code broke
            # we want to notify ourselves of the error detail and tell the user something vague
            notify_exception(None, "Unexpected error sending repeat record request")
            return self.handle_response(Exception("Internal Server Error"), repeat_record)
        else:
            return self.handle_response(response, repeat_record)

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


def _get_state(self):
    state = RECORD_PENDING_STATE
    if self.succeeded and self.cancelled:
        state = RECORD_EMPTY_STATE
    elif self.succeeded:
        state = RECORD_SUCCESS_STATE
    elif self.cancelled:
        state = RECORD_CANCELLED_STATE
    elif self.failure_reason:
        state = RECORD_FAILURE_STATE
    return state


def set_state(self, value):
    if value == RECORD_EMPTY_STATE:
        self.succeeded = True
        self.cancelled = True
        self.failure_reason = ""
    elif value == RECORD_SUCCESS_STATE:
        self.succeeded = True
        self.cancelled = False
        self.failure_reason = ""
    elif value == RECORD_CANCELLED_STATE:
        self.succeeded = False
        self.cancelled = True
        self.failure_reason = ""
    elif value == RECORD_FAILURE_STATE:
        self.succeeded = False
        self.cancelled = False
        try:
            reason = self.failure_reason
        except AssertionError:
            pass  # HACK jsonobject/base_properties.pyx:73
        else:
            if not reason:
                self.failure_reason = "Unknown"
    else:
        assert value == RECORD_PENDING_STATE
        self.succeeded = False
        self.cancelled = False
        self.failure_reason = ""


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
        return (self.success_response if self.succeeded else self.failure_reason) or ''

    @message.setter
    def message(self, value):
        if self.succeeded:
            self.success_response = value
        else:
            self.failure_reason = value

    state = property(_get_state, set_state)

    @property
    def created_at(self):
        # Used by .../case/partials/repeat_records.html
        return self.datetime

    @created_at.setter
    def created_at(self, value):
        self.datetime = value


class RepeaterIdProperty(StringProperty):

    def __set__(self, instance, value):
        super().__set__(instance, value)
        instance.__dict__.pop("repeater", None)


class RepeatRecord(SyncCouchToSQLMixin, Document):
    """
    An record of a particular instance of something that needs to be forwarded
    with a link to the proper repeater object
    """

    domain = StringProperty()
    repeater_id = RepeaterIdProperty()
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

    @classmethod
    def _migration_get_fields(cls):
        return ["domain", "payload_id", "registered_at", "state"]

    def _migration_sync_to_sql(self, sql_object, save=True):
        sql_object.repeater_id = uuid.UUID(self.repeater_id)
        sql_object.next_check = None if self.succeeded or self.cancelled else self.next_check
        return super()._migration_sync_to_sql(sql_object, save=save)

    @classmethod
    def _migration_get_submodels(cls):
        return [SubModelSpec(
            "attempt_set",
            SQLRepeatRecordAttempt,
            ["state", "message", "created_at"],
            "attempts",
            RepeatRecordAttempt,
            ["state", "message", "created_at"],
        )]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLRepeatRecord

    def save(self, *args, sync_attempts=False, **kw):
        with enable_attempts_sync_to_sql(self, sync_attempts):
            return super().save(*args, **kw)

    def _migration_sync_submodels_to_sql(self, sql_object):
        if self._should_sync_attempts:
            super()._migration_sync_submodels_to_sql(sql_object)

    @property
    def record_id(self):
        return self._id

    @property
    def next_attempt_at(self):
        return self.next_check

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

    @cached_property
    def repeater(self):
        try:
            return Repeater.objects.get(id=self.repeater_id)
        except Repeater.DoesNotExist:
            return None

    def is_repeater_deleted(self):
        try:
            return Repeater.all_objects.values_list("is_deleted", flat=True).get(id=self.repeater_id)
        except Repeater.DoesNotExist:
            return True

    @property
    def url(self):
        warnings.warn("RepeatRecord.url is deprecated. Use Repeater.get_url instead", DeprecationWarning)
        if self.repeater:
            return self.repeater.get_url(self)

    state = property(_get_state, set_state)

    @property
    def exceeded_max_retries(self):
        return (self.state == RECORD_FAILURE_STATE and self.overall_tries
                >= self.max_possible_tries)

    @property
    def registered_at(self):
        return self.registered_on or datetime.fromtimestamp(0)

    @registered_at.setter
    def registered_at(self, value):
        self.registered_on = value

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
        try:
            record_id = SQLRepeatRecord.objects.values("id").get(couch_id=self._id)["id"]
        except SQLRepeatRecord.DoesNotExist:
            with enable_attempts_sync_to_sql(self, True):
                self._migration_do_sync()
        else:
            SQLRepeatRecordAttempt.objects.create(
                repeat_record_id=record_id,
                state=attempt.state,
                message=attempt.message,
                created_at=attempt.created_at,
            )

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
        # Mark as cancelled and successful if it was an empty payload with nothing to send
        return RepeatRecordAttempt(
            cancelled=(response.status_code == 204),
            datetime=now,
            failure_reason=None,
            success_response=format_response(response),
            next_check=None,
            succeeded=True,
            info=self.get_attempt_info(),
        )

    def handle_failure(self, response):
        """Do something with the response if the repeater fails
        """
        return self._make_failure_attempt(format_response(response), response)

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

    def _is_ready(self):
        return self.next_check < datetime.utcnow()

    def _already_processed(self):
        return self.succeeded or self.cancelled or self.next_check is None

    def attempt_forward_now(self, *, is_retry=False, fire_synchronously=False):
        from corehq.motech.repeaters.tasks import (
            process_repeat_record,
            retry_process_repeat_record,
        )

        if self._already_processed() or not self._is_ready():
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
        task = retry_process_repeat_record if is_retry else process_repeat_record

        if fire_synchronously:
            task(self._id, self.domain)
        else:
            task.delay(self._id, self.domain)

    def requeue(self):
        self.cancelled = False
        self.succeeded = False
        self.failure_reason = ''
        self.overall_tries = 0
        self.next_check = datetime.utcnow()


def is_sql_id(value):
    return not isinstance(value, str) or (value.isdigit() and len(value) != 32)


@contextmanager
def enable_attempts_sync_to_sql(obj, value):
    assert not hasattr(obj, "_should_sync_attempts")
    obj._should_sync_attempts = value
    try:
        yield
    finally:
        del obj._should_sync_attempts


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


class SQLRepeatRecord(SyncSQLToCouchMixin, models.Model):
    domain = models.CharField(max_length=126)
    couch_id = models.CharField(max_length=36, null=True, blank=True)
    payload_id = models.CharField(max_length=255)
    repeater = models.ForeignKey(Repeater,
                                 on_delete=DB_CASCADE,
                                 db_column="repeater_id_",
                                 related_name='repeat_records')
    state = models.PositiveSmallIntegerField(choices=State.choices, default=State.Pending)
    registered_at = models.DateTimeField()
    next_check = models.DateTimeField(null=True, default=None)
    max_possible_tries = models.IntegerField(default=MAX_BACKOFF_ATTEMPTS)

    objects = RepeatRecordManager()

    class Meta:
        db_table = 'repeaters_repeatrecord'
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['payload_id']),
            models.Index(fields=['registered_at']),
            models.Index(
                name="next_check_not_null",
                fields=["next_check"],
                condition=models.Q(next_check__isnull=False),
            )
        ]
        constraints = [
            models.UniqueConstraint(
                name="unique_couch_id",
                fields=['couch_id'],
                condition=models.Q(couch_id__isnull=False),
            ),
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

    @classmethod
    def _migration_get_couch_model_class(cls):
        return RepeatRecord

    @classmethod
    def _migration_get_fields(cls):
        return [
            "domain",
            "payload_id",
            "registered_at",
            "next_check",
            "state",
            "failure_reason",
            "overall_tries",
        ]

    def _migration_sync_to_couch(self, couch_object, save=True):
        couch_object.repeater_id = self.repeater.repeater_id
        return super()._migration_sync_to_couch(couch_object, save=save)

    def requeue(self):
        # Changing "success" to "pending" and "cancelled" to "failed"
        # preserves the value of `self.failure_reason`.
        if self.succeeded:
            self.state = State.Pending
        elif self.state == State.Cancelled:
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
        self.repeater.reset_next_attempt()
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
        self.repeater.reset_next_attempt()
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
        self.repeater.set_next_attempt()
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

    def add_payload_exception_attempt(self, message, tb_str):
        self.attempt_set.create(
            state=State.Cancelled,
            message=message,
            traceback=tb_str,
        )
        self.state = State.Cancelled
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
    def next_attempt_at(self):
        return self.repeater.next_attempt_at

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
    def overall_tries(self):
        return self.num_attempts

    @overall_tries.setter
    def overall_tries(self, ignored):
        pass

    @property
    def exceeded_max_retries(self):
        return self.state == State.Fail and self.num_attempts >= self.max_possible_tries

    @property
    def repeater_type(self):
        return self.repeater.repeater_type

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

    def try_now(self):
        # TODO rename to should_try_now
        return self.state != State.Success

    def attempt_forward_now(self, *, is_retry=False, fire_synchronously=False):
        from corehq.motech.repeaters.tasks import (
            process_repeat_record,
            retry_process_repeat_record,
        )

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
        self.add_server_failure_attempt(format_response(response))

    def handle_exception(self, exception):
        self.add_client_failure_attempt(str(exception))

    def handle_payload_exception(self, exception):
        self.add_client_failure_attempt(str(exception), retry=False)

    def add_attempt(self, attempt):
        assert attempt is None, "SQL attempts are added/saved on create"

    def cancel(self):
        self.state = State.Cancelled
        self.next_check = None

    def get_payload(self):
        return self.repeater.get_payload(self)

    def postpone_by(self, duration):
        self.next_check = datetime.utcnow() + duration
        self.save()


class SQLRepeatRecordAttempt(models.Model):
    repeat_record = models.ForeignKey(
        SQLRepeatRecord, on_delete=DB_CASCADE, related_name="attempt_set")
    state = models.PositiveSmallIntegerField(choices=State.choices)
    message = models.TextField(blank=True, default='')
    traceback = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'repeaters_repeatrecordattempt'
        ordering = ['created_at']


@receiver(models.signals.pre_save, sender=SQLRepeatRecordAttempt)
def _register_new_attempt_to_clear_cache(sender, instance, **kwargs):
    record = instance._meta.get_field("repeat_record").get_cached_value(instance, None)
    if instance._state.adding and record is not None:
        instance._record_with_new_attempt = record


@receiver(models.signals.post_save, sender=SQLRepeatRecordAttempt)
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


def attempt_forward_now(repeater: Repeater):  # unused
    from corehq.motech.repeaters.tasks import process_repeater

    if not domain_can_forward(repeater.domain):
        return
    if not repeater.is_ready:  # only place that uses Repeater.is_ready
        return
    process_repeater.delay(repeater.id.hex)


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
    return repeat_record.state in (State.Success, State.Cancelled, State.Empty)  # Don't retry


def has_failed(record):
    return record.state in (State.Fail, State.Cancelled)


def format_response(response):
    if not is_response(response):
        return ''
    response_text = getattr(response, "text", "")[:MAX_REQUEST_LOG_LENGTH]
    if response_text:
        return f'{response.status_code}: {response.reason}\n{response_text}'
    return f'{response.status_code}: {response.reason}'


def is_response(duck):
    """
    Returns True if ``duck`` has the attributes of a Requests response
    instance that this module uses, otherwise False.
    """
    return hasattr(duck, 'status_code') and hasattr(duck, 'reason')


def are_repeat_records_migrated(domain) -> bool:
    return True


def domain_can_forward(domain):
    return domain and (
        domain_has_privilege(domain, ZAPIER_INTEGRATION)
        or domain_has_privilege(domain, DATA_FORWARDING)
    )
