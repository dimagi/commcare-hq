from __future__ import absolute_import
from django.core.exceptions import ValidationError
import pytz
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser, WebUser, AnonymousCouchUser
from corehq.util.global_request import get_request
from corehq.util.soft_assert import soft_assert
import six


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
    if couch_user_or_id and not isinstance(couch_user_or_id, AnonymousCouchUser):
        if isinstance(couch_user_or_id, CouchUser):
            requesting_user = couch_user_or_id
        else:
            assert isinstance(couch_user_or_id, six.string_types)
            try:
                requesting_user = WebUser.get_by_user_id(couch_user_or_id)
            except CouchUser.AccountTypeError:
                requesting_user = None

        if requesting_user:
            domain_membership = requesting_user.get_domain_membership(domain)
            if domain_membership:
                return coerce_timezone_value(domain_membership.timezone)

    return get_timezone_for_domain(domain)
