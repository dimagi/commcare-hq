import json
import os
from django.test.testcases import TestCase
from custom.ilsgateway.api import Product, ILSUser, SMSUser


class ProductApiTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')

    def testParseProductJSON(self):
        with open(os.path.join(self.datapath, 'sample_product.json')) as f:
            ilsgateway_program = Product.from_json(json.loads(f.read()))
        self.assertEqual(ilsgateway_program.name, "Condoms")
        self.assertEqual(ilsgateway_program.units, "each")
        self.assertEqual(ilsgateway_program.sms_code, "cond")
        self.assertEqual(ilsgateway_program.description, "Condoms")
        self.assertEqual(ilsgateway_program.is_active, True)


    def testParseWebUserJSON(self):
        with open(os.path.join(self.datapath, 'sample_webuser.json')) as f:
            webuser = ILSUser.from_json(json.loads(f.read()))
        self.assertEqual(webuser.first_name, "ILS")
        self.assertEqual(webuser.last_name, "Gateway")
        self.assertEqual(webuser.username, "ilsgateway")
        self.assertEqual(webuser.email, "ilsgateway@gmail.com")
        self.assertEqual(webuser.password, "sha1$44fa5$ae4f55a31a768f14dd552be204058f34756c8d6")
        self.assertEqual(bool(webuser.is_staff), True)
        self.assertEqual(bool(webuser.is_active), True)
        self.assertEqual(bool(webuser.is_superuser), True)
        self.assertEqual(webuser.last_login, "2014-04-28 18:17:46.13074+02")
        self.assertEqual(webuser.date_joined, "2011-08-03 10:55:22+02")
        self.assertEqual(webuser.location, 1)
        self.assertEqual(webuser.supply_point, "")

    def testParseSMSUserJSON(self):
        with open(os.path.join(self.datapath, 'sample_smsuser.json')) as f:
            smsuser = SMSUser.from_json(json.loads(f.read()))
        self.assertEqual(smsuser.id, 1)
        self.assertEqual(smsuser.name, "Test user")
        self.assertEqual(smsuser.role, "ic")
        self.assertEqual(smsuser.supply_point, 79)
        self.assertEqual(smsuser.email, "test@gmail.com")
        self.assertEqual(bool(smsuser.is_active), True)
        self.assertEqual(smsuser.phone_numbers, ["4224242442"])

