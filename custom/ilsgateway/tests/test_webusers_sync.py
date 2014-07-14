import json
import os
from django.test import TestCase
from corehq import Domain
from corehq.apps.commtrack.tests.util import bootstrap_domain as initial_bootstrap
from corehq.apps.users.models import WebUser
from custom.ilsgateway.api import ILSUser
from custom.ilsgateway.commtrack import sync_ilsgateway_webusers

TEST_DOMAIN = 'ilsgateway-commtrack-webusers-test'


class WebUsersSyncTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')
        initial_bootstrap(TEST_DOMAIN)

        for user in WebUser.by_domain(TEST_DOMAIN):
            user.delete()

    def test_create_webuser(self):
        with open(os.path.join(self.datapath, 'sample_webuser.json')) as f:
            webuser = ILSUser.from_json(json.loads(f.read()))

        self.assertEqual(0, len(WebUser.by_domain(TEST_DOMAIN)))
        ilsgateway_webuser = sync_ilsgateway_webusers(TEST_DOMAIN, webuser)
        self.assertEqual(webuser.email, ilsgateway_webuser.username)
        self.assertEqual(webuser.password, ilsgateway_webuser.password)
        self.assertEqual(webuser.first_name, ilsgateway_webuser.first_name)
        self.assertEqual(webuser.last_name, ilsgateway_webuser.last_name)
        self.assertEqual(webuser.is_active, ilsgateway_webuser.is_active)
        self.assertEqual(webuser.is_superuser, ilsgateway_webuser.is_superuser)
        self.assertEqual(webuser.is_staff, ilsgateway_webuser.is_staff)
        #self.assertEqual(webuser.location, ilsgateway_webuser.location)
        #self.assertEqual(webuser.supply_point, ilsgateway_webuser.supply_point)
        domain_name = ilsgateway_webuser.get_domains()[0]
        self.assertEqual(TEST_DOMAIN, domain_name)
        self.assertEqual(None, ilsgateway_webuser.get_domain_membership(TEST_DOMAIN).role_id)
