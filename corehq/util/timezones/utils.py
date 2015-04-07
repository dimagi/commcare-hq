from django.core.exceptions import ValidationError
import pytz
import datetime
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser, WebUser


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


def get_timezone_for_user(couch_user_or_id, domain):
    # todo cleanup
    timezone = None
    if couch_user_or_id:
        if isinstance(couch_user_or_id, CouchUser):
            requesting_user = couch_user_or_id
        else:
            assert isinstance(couch_user_or_id, basestring)
            try:
                requesting_user = WebUser.get_by_user_id(couch_user_or_id)
            except CouchUser.AccountTypeError:
                return pytz.utc
        domain_membership = requesting_user.get_domain_membership(domain)
        if domain_membership:
            timezone = coerce_timezone_value(domain_membership.timezone)

    if not timezone:
        current_domain = Domain.get_by_name(domain)
        try:
            timezone = coerce_timezone_value(current_domain.default_timezone)
        except pytz.UnknownTimeZoneError:
            timezone = pytz.utc
    return timezone
