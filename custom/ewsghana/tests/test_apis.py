from decimal import Decimal
import json
import os
from django.test.testcases import TestCase
from custom.ewsghana.api import Location, EWSUser, SMSUser
from custom.ilsgateway.api import Product, StockTransaction, ProductStock


class ApisTest(TestCase):

    def setUp(self):
        self.datapath = os.path.join(os.path.dirname(__file__), 'data')

    def test_parse_product_json(self):
        with open(os.path.join(self.datapath, 'sample_products.json')) as f:
            product = Product(json.loads(f.read())[0])
        self.assertEqual(product.name, "Abacavir 300mg")
        self.assertEqual(product.units, "Tablet")
        self.assertEqual(product.sms_code, "abc")
        self.assertEqual(product.description, "Abacavir 300mg")
        self.assertEqual(product.is_active, True)

    def test_parse_location_json(self):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            location = Location(json.loads(f.read())[1])
        self.assertEqual(location.id, 620)
        self.assertEqual(location.name, "Test facility")
        self.assertEqual(location.type, "facility")
        self.assertEqual(location.parent_id, 369)
        self.assertEqual(location.latitude, "")
        self.assertEqual(location.longitude, "")
        self.assertEqual(location.code, "testfacility")
        self.assertEqual(location.supervised_by, 591)
        self.assertEqual(location.groups, [])

    def test_parse_webuser_json(self):
        with open(os.path.join(self.datapath, 'sample_webusers.json')) as f:
            webusers = EWSUser(json.loads(f.read())[0])
        self.assertEqual(webusers.email, 'test1@yahoo.co.uk')
        self.assertEqual(webusers.first_name, 'Test1')
        self.assertEqual(webusers.last_name, 'Test1')
        self.assertEqual(webusers.is_active, True)
        self.assertEqual(webusers.is_staff, False)
        self.assertEqual(webusers.is_superuser, False)
        self.assertEqual(webusers.location, 319)
        self.assertEqual(webusers.organization, 'TestOrg1')
        self.assertEqual(webusers.password, 'sha1$4b8dd$8acea54703614eea2fbb4bf7fd6ee9465a67ff53')
        self.assertEqual(webusers.sms_notifications, True)
        self.assertEqual(webusers.supply_point, None)
        self.assertEqual(webusers.username, 'test1')

    def test_parse_sms_user_json(self):
        with open(os.path.join(self.datapath, 'sample_smsusers.json')) as f:
            smsuser = SMSUser(json.loads(f.read())[0])
        self.assertEqual(smsuser.id, 2342)
        self.assertEqual(smsuser.name, "Test1")
        self.assertEqual(smsuser.role, "Other")
        self.assertEqual(smsuser.supply_point, 324)
        self.assertEqual(smsuser.email, None)
        self.assertEqual(smsuser.is_active, "True")
        self.assertEqual(smsuser.phone_numbers, ["+2222222222"])

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
