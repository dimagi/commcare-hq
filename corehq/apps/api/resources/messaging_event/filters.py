import functools

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from tastypie.exceptions import BadRequest, InvalidFilterError

from corehq.apps.api.util import make_date_filter, django_date_filter
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.sms.util import validate_phone_number


SLUG_FILTER_ERROR_MESSAGE = _("'{value}' is an invalid value for the '{filter_name}' filter")


def filter_query(query, request_data):
    filters = {}
    for key, value in request_data.items():
        if key in SIMPLE_FILTERS:
            filters.update(SIMPLE_FILTERS[key](key, value))
        else:
            for consumer in COMPOUND_FILTERS:
                filters.update(consumer(key, value))

    # filters can be django kwarg filters e.g. {"date__lte": value} or
    # Q objects e.g. {"date": Q(date__lte=value) | Q(date__gt=value)
    native_filters = []
    for key, value in list(filters.items()):
        if isinstance(value, Q):
            native_filters.append(filters.pop(key))
    query = query.filter(**filters)
    if native_filters:
        query = query.filter(*native_filters)
    return query


def _get_date_filter_consumer(api_field, query_field=None):
    """date.{lt, lte, gt, gte}=<ISO DATE>"""

    query_field = query_field or api_field
    date_filter = make_date_filter(functools.partial(django_date_filter, field_name=query_field))

    def _date_consumer(key, value):
        if '.' in key and key.split(".")[0] == api_field:
            prefix, qualifier = key.split(".", maxsplit=1)
            try:
                return date_filter(qualifier, value)
            except ValueError as e:
                raise InvalidFilterError(str(e))

        return {}

    return _date_consumer


def _get_source_filter_consumer():
    """source=<SOURCE SLUG>"""
    # match functionality in corehq.apps.reports.standard.sms.MessagingEventsReport.get_filters
    expansions = {
        MessagingEvent.SOURCE_OTHER: [MessagingEvent.SOURCE_FORWARDED],
        MessagingEvent.SOURCE_BROADCAST: [
            MessagingEvent.SOURCE_SCHEDULED_BROADCAST,
            MessagingEvent.SOURCE_IMMEDIATE_BROADCAST
        ],
        MessagingEvent.SOURCE_REMINDER: [MessagingEvent.SOURCE_CASE_RULE]
    }
    return _make_slug_filter_consumer(
        "source", MessagingEvent.SOURCE_SLUGS, "parent__source__in", expansions
    )


def _get_content_type_filter_consumer():
    """content_type=<CONTENT TYPE SLUG>"""
    # match functionality in corehq.apps.reports.standard.sms.MessagingEventsReport.get_filters
    expansions = {
        MessagingEvent.CONTENT_SMS_SURVEY: [
            MessagingEvent.CONTENT_SMS_SURVEY,
            MessagingEvent.CONTENT_IVR_SURVEY,
        ],
        MessagingEvent.CONTENT_SMS: [
            MessagingEvent.CONTENT_SMS,
            MessagingEvent.CONTENT_PHONE_VERIFICATION,
            MessagingEvent.CONTENT_ADHOC_SMS,
            MessagingEvent.CONTENT_API_SMS,
            MessagingEvent.CONTENT_CHAT_SMS
        ],
    }
    return _make_slug_filter_consumer(
        "content_type", MessagingEvent.CONTENT_TYPE_SLUGS, "content_type__in", expansions
    )


def _make_slug_filter_consumer(filter_key, slug_dict, model_filter_arg, expansions=None):
    slug_values = {v: k for k, v in slug_dict.items()}

    def _consumer(key, value):
        if key != filter_key:
            return {}

        values = value.split(',')
        vals = [slug_values[val] for val in values if val in slug_values]
        if vals:
            for key, extras in (expansions or {}).items():
                if key in vals:
                    vals.extend(extras)
            return {model_filter_arg: vals}

    return _consumer


def _status_filter_consumer(key, value):
    """status=<STATUS SLUG>

    Status filtering is applied to the event as well as to the messages / XFormSession.
    """
    slug_values = {v: k for k, v in MessagingEvent.STATUS_SLUGS.items()}
    if key != "status":
        return {}

    try:
        model_value = slug_values[value]
    except KeyError:
        raise BadRequest(SLUG_FILTER_ERROR_MESSAGE.format(value=value, filter_name='status'))

    # match functionality in corehq.pps.reports.standard.sms.MessagingEventsReport.get_filters
    if model_value == MessagingEvent.STATUS_ERROR:
        return {"status": (Q(status=model_value) | Q(sms__error=True))}
    elif model_value == MessagingEvent.STATUS_IN_PROGRESS:
        # We need to check for id__isnull=False below because the
        # query we make in this report has to do a left join, and
        # in this particular filter we can only validly check
        # session_is_open=True if there actually are
        # subevent and xforms session records
        return {"status": (
            Q(status=model_value)
            | (Q(xforms_session__id__isnull=False) & Q(xforms_session__session_is_open=True))
        )}
    elif model_value == MessagingEvent.STATUS_NOT_COMPLETED:
        return {"status": (
            Q(status=model_value)
            | (Q(xforms_session__session_is_open=False) & Q(xforms_session__submission_id__isnull=True))
        )}
    else:
        return {"status": model_value}


def _make_simple_consumer(filter_name, model_filter_arg, validator=None):
    def _consumer(key, value):
        if key != filter_name:
            return {}

        value = value.strip()

        if validator:
            try:
                validator(value)
            except ValidationError:
                raise BadRequest(SLUG_FILTER_ERROR_MESSAGE.format(value=value, filter_name=filter_name))

        return {model_filter_arg: value}

    return _consumer


COMPOUND_FILTERS = [
    _get_date_filter_consumer("date"),
    _get_date_filter_consumer("date_last_activity"),
]

SIMPLE_FILTERS = {
    "source": _get_source_filter_consumer(),
    "content_type": _get_content_type_filter_consumer(),
    "status": _status_filter_consumer,
    "error_code": _make_simple_consumer("error_code", "error_code"),
    "email_address": _make_simple_consumer(
        "email_address", "email__recipient_address", validate_email
    ),
    "phone_number": _make_simple_consumer(
        "phone_number", "sms__phone_number__contains", validate_phone_number
    ),
    "case_id": _make_simple_consumer("case_id", "case_id")
}
