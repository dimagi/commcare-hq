from decimal import Decimal
import json
import os
from django.test.testcases import TestCase
from custom.ilsgateway.api import Product, ILSUser, SMSUser, Location, ProductStock, StockTransaction


class ApisTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')

    def test_parse_product_json(self):
        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            ilsgateway_program = Product(json.loads(f.read())[0])
        self.assertEqual(ilsgateway_program.name, "Condoms")
        self.assertEqual(ilsgateway_program.units, "each")
        self.assertEqual(ilsgateway_program.sms_code, "cond")
        self.assertEqual(ilsgateway_program.description, "Condoms")
        self.assertEqual(ilsgateway_program.is_active, True)

    def test_parse_web_user_json(self):
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webuser = ILSUser(json.loads(f.read())[0])
        self.assertEqual(webuser.first_name, "ILS")
        self.assertEqual(webuser.last_name, "Gateway")
        self.assertEqual(webuser.username, "ilsgateway")
        self.assertEqual(webuser.email, "ilsgateway@gmail.com")
        self.assertEqual(webuser.password, "sha1$44fa5$ae4f55a31a768f14dd552be204058f34756c8d6")
        self.assertEqual(bool(webuser.is_staff), False)
        self.assertEqual(bool(webuser.is_active), True)
        self.assertEqual(bool(webuser.is_superuser), False)
        self.assertEqual(webuser.last_login, "2014-04-28 18:17:46.13074+02")
        self.assertEqual(webuser.date_joined, "2011-08-03 10:55:22+02")
        self.assertEqual(webuser.location, 1)
        self.assertEqual(webuser.supply_point, None)

    def test_parse_sms_user_json(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])
        self.assertEqual(smsuser.id, 1)
        self.assertEqual(smsuser.name, "Test user")
        self.assertEqual(smsuser.role, "ic")
        self.assertEqual(smsuser.supply_point, 79)
        self.assertEqual(smsuser.email, "test@gmail.com")
        self.assertEqual(smsuser.is_active, "True")
        self.assertEqual(smsuser.phone_numbers, ["4224242442"])

    def test_parse_location_json(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])
        self.assertEqual(location.id, 1)
        self.assertEqual(location.name, "MOHSW")
        self.assertEqual(location.type, "MOHSW")
        self.assertEqual(location.parent_id, None)
        self.assertEqual(location.latitude, "-10.6676087700")
        self.assertEqual(location.longitude, "39.1621900200")
        self.assertEqual(location.code, "MOHSW-MOHSW")

    def test_parse_productstock_json(self):
        with open(os.path.join(self.datapath, 'sample_productstocks.json')) as f:
            product_stock = ProductStock(json.loads(f.read())[0])
        self.assertEqual(None, product_stock.auto_monthly_consumption)
        self.assertEqual("2011-09-01T22:41:35.039236", product_stock.last_modified)
        self.assertEqual("ip", product_stock.product)
        self.assertEqual(0.0, product_stock.quantity)
        self.assertEqual(68, product_stock.supply_point)

    def test_parse_stocktransaction_json(self):
        with open(os.path.join(self.datapath, 'sample_stocktransactions.json')) as f:
            stock_transaction = StockTransaction(json.loads(f.read())[0])
        self.assertEqual(Decimal(0), stock_transaction.beginning_balance)
        self.assertEqual("2010-12-03T07:45:59.139272", stock_transaction.date)
        self.assertEqual(Decimal(63), stock_transaction.ending_balance)
        self.assertEqual("pp", stock_transaction.product)
        self.assertEqual(Decimal(63), stock_transaction.quantity)
        self.assertEqual(39, stock_transaction.supply_point)
        self.assertEqual("stock on hand", stock_transaction.report_type)

