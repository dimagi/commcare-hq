from django.test import TestCase
from corehq.apps.commtrack.tests.util import bootstrap_domain, make_loc
from custom.ewsghana.handler import handle
from custom.ewsghana.utils import bootstrap_user

TEST_DOMAIN = 'ews-handler-test'


class HandlerTest(TestCase):

    def setUp(self):
        domain = bootstrap_domain(TEST_DOMAIN)
        loc = make_loc(code="garms", name="Test RMS", type="Regional Medical Store", domain=domain.name)
        self.user = bootstrap_user(username='testuser', phone_number='323232', domain=domain.name, home_loc=loc)

    def test_not_ews_domain(self):
        self.assertFalse(handle(self.user.get_verified_number(), "soh dp 40.0"))
        self.assertFalse(handle(self.user.get_verified_number(), "dp 40.0"))
