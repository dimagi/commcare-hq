import datetime
import dateutil
import pytz
from functools import reduce
from memoized import memoized

from django.core.exceptions import ValidationError

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser, WebUser
from corehq.util.global_request import get_request
from corehq.util.soft_assert import soft_assert
from corehq.util.dates import iso_string_to_datetime


def coerce_timezone_value(value):
    try:
        return pytz.timezone(str(value))
    except pytz.UnknownTimeZoneError:
        raise ValidationError("Unknown timezone")


def validate_timezone_max_length(max_length, zones):
    def reducer(x, y):
        return x and (len(y) <= max_length)
    if not reduce(reducer, zones, True):
        raise Exception("corehq.apps.timezones.fields.TimeZoneField MAX_TIMEZONE_LENGTH is too small")


def get_timezone_for_request(request=None):
    if request is None:
        request = get_request()

    user = getattr(request, 'couch_user', None)
    domain = getattr(request, 'domain', None)

    if user or domain:
        return get_timezone_for_user(user, domain)
    else:
        return None


def get_timezone_for_domain(domain):
    current_domain = Domain.get_by_name(domain)
    _assert = soft_assert('@'.join(['droberts', 'dimagi.com']))
    if _assert(current_domain, "get_timezone_for_domain passed fake domain",
               {'domain': domain}):
        return coerce_timezone_value(current_domain.default_timezone)
    else:
        return pytz.UTC


def get_timezone_for_user(couch_user_or_id, domain):
    if couch_user_or_id:
        if isinstance(couch_user_or_id, CouchUser):
            requesting_user = couch_user_or_id
        else:
            assert isinstance(couch_user_or_id, str), type(couch_user_or_id)
            try:
                requesting_user = WebUser.get_by_user_id(couch_user_or_id)
            except CouchUser.AccountTypeError:
                requesting_user = None

        if requesting_user:
            domain_membership = requesting_user.get_domain_membership(domain)
            if domain_membership and domain_membership.override_global_tz:
                return coerce_timezone_value(domain_membership.timezone)

    return get_timezone_for_domain(domain)


@memoized
def get_timezone(request, domain):
    if not domain:
        return pytz.utc
    else:
        try:
            return get_timezone_for_user(request.couch_user, domain)
        except AttributeError:
            return get_timezone_for_user(None, domain)


def parse_date(date_string):
    try:
        return iso_string_to_datetime(date_string)
    except Exception:
        try:
            date_obj = dateutil.parser.parse(date_string)
            if isinstance(date_obj, datetime.datetime):
                return date_obj.replace(tzinfo=None)
            else:
                return date_obj
        except Exception:
            return date_string
