from datetime import datetime

import pytz
from unittest.mock import patch

from django.test import SimpleTestCase
import testil

from corehq.apps.users.models import WebUser, DomainMembership
from corehq.util.timezones.utils import get_timezone_for_user, parse_date

DOMAIN_TIMEZONE = pytz.timezone('Asia/Kolkata')


@patch('corehq.util.timezones.utils.get_timezone_for_domain', lambda x: DOMAIN_TIMEZONE)
@patch('corehq.apps.users.models._AuthorizableMixin.get_domain_membership')
class GetTimezoneForUserTest(SimpleTestCase):
    def test_no_user(self, _):
        self.assertEqual(get_timezone_for_user(None, "test"), DOMAIN_TIMEZONE)

    def test_user_with_no_domain_membership(self, domain_membership_mock):
        couch_user = WebUser()
        domain_membership_mock.return_value = None
        self.assertEqual(get_timezone_for_user(couch_user, "test"), DOMAIN_TIMEZONE)

    def test_user_with_domain_membership(self, domain_membership_mock):
        couch_user = WebUser()
        domain_membership = DomainMembership()
        domain_membership_timezone = pytz.timezone('America/New_York')
        domain_membership.timezone = 'America/New_York'
        domain_membership_mock.return_value = domain_membership

        # if not override_global_tz
        self.assertEqual(get_timezone_for_user(couch_user, "test"), DOMAIN_TIMEZONE)

        # if override_global_tz
        domain_membership.override_global_tz = True
        self.assertEqual(get_timezone_for_user(couch_user, "test"), domain_membership_timezone)


def test_parse_date_iso_datetime():
    parsed = parse_date('2022-04-06T12:13:14Z')
    testil.eq(parsed, datetime(2022, 4, 6, 12, 13, 14))
    # `date` is timezone naive
    testil.eq(parsed.tzinfo, None)


def test_parse_date_noniso_datetime():
    parsed = parse_date('Apr 06, 2022 12:13:14 UTC')
    testil.eq(parsed, datetime(2022, 4, 6, 12, 13, 14))
    # `date` is timezone naive
    testil.eq(parsed.tzinfo, None)


def test_parse_date_date():
    parsed = parse_date('2022-04-06')
    testil.eq(parsed, datetime(2022, 4, 6, 0, 0, 0))


def test_parse_date_str():
    parsed = parse_date('broken')
    testil.eq(parsed, 'broken')


def test_parse_date_none():
    parsed = parse_date(None)
    testil.eq(parsed, None)


def test_parse_date_int():
    parsed = parse_date(4)
    testil.eq(parsed, 4)
