import pytz
from mock import patch

from django.test import SimpleTestCase, override_settings

from corehq.apps.users.models import WebUser, DomainMembership
from corehq.util.timezones.utils import get_timezone_for_user

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
        self.assertEqual(get_timezone_for_user(couch_user, "test"), domain_membership_timezone)
        with override_settings(SERVER_ENVIRONMENT='icds'):
            self.assertEqual(get_timezone_for_user(couch_user, "test"), DOMAIN_TIMEZONE)

        # if override_global_tz
        domain_membership.override_global_tz = True
        self.assertEqual(get_timezone_for_user(couch_user, "test"), domain_membership_timezone)
