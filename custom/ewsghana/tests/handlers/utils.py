import datetime

from django.test.testcases import TestCase

from casexml.apps.stock.models import DocDomainMapping
from casexml.apps.stock.models import StockReport, StockTransaction
from couchdbkit.exceptions import ResourceNotFound
from couchforms.models import XFormInstance

from corehq.apps.accounting import generator
from corehq.apps.commtrack.models import CommtrackConfig, CommtrackActionConfig, StockState, ConsumptionConfig
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.consumption.shortcuts import set_default_consumption_for_supply_point
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location, SQLLocation, LocationType
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.sms.tests.util import setup_default_sms_test_backend, delete_domain_phone_numbers
from corehq.apps.users.models import CommCareUser

from custom.ewsghana.models import EWSGhanaConfig, FacilityInCharge
from custom.ewsghana.utils import prepare_domain, bootstrap_user
from custom.logistics.tests.test_script import TestScript

TEST_DOMAIN = 'ewsghana-test'


class EWSTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        cls.sms_backend_mapping.delete()
        cls.backend.delete()
        generator.delete_all_subscriptions()


class EWSScriptTest(EWSTestCase, TestScript):

    def _create_stock_state(self, product, consumption):
        xform = XFormInstance.get('test-xform')
        loc = Location.by_site_code(TEST_DOMAIN, 'garms')
        now = datetime.datetime.utcnow()
        report = StockReport(
            form_id=xform._id,
            date=(now - datetime.timedelta(days=10)).replace(second=0, microsecond=0),
            type='balance',
            domain=TEST_DOMAIN
        )
        report.save()
        stock_transaction = StockTransaction(
            case_id=loc.linked_supply_point().get_id,
            product_id=product.get_id,
            sql_product=SQLProduct.objects.get(product_id=product.get_id),
            section_id='stock',
            type='stockonhand',
            stock_on_hand=2 * consumption,
            report=report
        )
        stock_transaction.save()

    def setUp(self):
        Product.get_by_code(TEST_DOMAIN, 'mc')
        Product.get_by_code(TEST_DOMAIN, 'lf')

    def tearDown(self):
        StockTransaction.objects.all().delete()
        StockReport.objects.all().delete()
        StockState.objects.all().delete()
        DocDomainMapping.objects.all().delete()

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        domain = prepare_domain(TEST_DOMAIN)

        p = Product(domain=domain.name, name='Jadelle', code='jd', unit='each')
        p.save()
        p2 = Product(domain=domain.name, name='Male Condom', code='mc', unit='each')
        p2.save()
        p3 = Product(domain=domain.name, name='Lofem', code='lf', unit='each')
        p3.save()
        p4 = Product(domain=domain.name, name='Ng', code='ng', unit='each')
        p4.save()
        p5 = Product(domain=domain.name, name='Micro-G', code='mg', unit='each')
        p5.save()

        Product(domain=domain.name, name='Ad', code='ad', unit='each').save()
        Product(domain=domain.name, name='Al', code='al', unit='each').save()
        Product(domain=domain.name, name='Qu', code='qu', unit='each').save()
        Product(domain=domain.name, name='Sp', code='sp', unit='each').save()
        Product(domain=domain.name, name='Rd', code='rd', unit='each').save()
        Product(domain=domain.name, name='Ov', code='ov', unit='each').save()
        Product(domain=domain.name, name='Ml', code='ml', unit='each').save()

        national = make_loc(code='country', name='Test national', type='country', domain=domain.name)
        region = make_loc(code='region', name='Test region', type='region', domain=domain.name, parent=national)
        loc = make_loc(code="garms", name="Test RMS", type="Regional Medical Store", domain=domain.name,
                       parent=national)
        loc.save()

        rms2 = make_loc(code="wrms", name="Test RMS 2", type="Regional Medical Store", domain=domain.name,
                        parent=region)
        rms2.save()

        cms = make_loc(code="cms", name="Central Medical Stores", type="Central Medical Store",
                       domain=domain.name, parent=national)
        cms.save()

        loc2 = make_loc(code="tf", name="Test Facility", type="CHPS Facility", domain=domain.name, parent=region)
        loc2.save()

        supply_point_id = loc.linked_supply_point().get_id
        supply_point_id2 = loc2.linked_supply_point().get_id

        cls.user1 = bootstrap_user(username='stella', first_name='test1', last_name='test1',
                                   domain=domain.name, home_loc=loc)
        cls.user2 = bootstrap_user(username='super', domain=domain.name, home_loc=loc2,
                                   first_name='test2', last_name='test2',
                                   phone_number='222222', user_data={'role': ['In Charge']})
        FacilityInCharge.objects.create(
            user_id=cls.user2.get_id,
            location=loc2.sql_location
        )
        cls.user3 = bootstrap_user(username='pharmacist', domain=domain.name, home_loc=loc2,
                                   first_name='test3', last_name='test3',
                                   phone_number='333333')
        cls.rms_user = bootstrap_user(username='rmsuser', domain=domain.name, home_loc=rms2,
                                      first_name='test4', last_name='test4',
                                      phone_number='44444')
        cls.cms_user = bootstrap_user(username='cmsuser', domain=domain.name, home_loc=cms,
                                      first_name='test5', last_name='test5',
                                      phone_number='55555')
        cls.region_user = bootstrap_user(username='regionuser', domain=domain.name, home_loc=region,
                                         first_name='test6', last_name='test6',
                                         phone_number='66666')
        cls.without_location = bootstrap_user(username='withoutloc', domain=domain.name, first_name='test7',
                                              last_name='test7', phone_number='77777')
        try:
            XFormInstance.get(docid='test-xform')
        except ResourceNotFound:
            xform = XFormInstance(_id='test-xform')
            xform.save()

        sql_location = loc.sql_location
        sql_location.products = []
        sql_location.save()

        sql_location = loc2.sql_location
        sql_location.products = []
        sql_location.save()

        sql_location = rms2.sql_location
        sql_location.products = []
        sql_location.save()

        sql_location = cms.sql_location
        sql_location.products = []
        sql_location.save()

        config = CommtrackConfig.for_domain(domain.name)
        config.use_auto_consumption = False
        config.individual_consumption_defaults = True
        config.actions.append(
            CommtrackActionConfig(
                action='receipts',
                keyword='rec',
                caption='receipts'
            )
        )
        config.consumption_config = ConsumptionConfig(
            use_supply_point_type_default_consumption=True,
            exclude_invalid_periods=True
        )
        config.save()

        set_default_consumption_for_supply_point(TEST_DOMAIN, p2.get_id, supply_point_id, 8)
        set_default_consumption_for_supply_point(TEST_DOMAIN, p3.get_id, supply_point_id, 5)

        set_default_consumption_for_supply_point(TEST_DOMAIN, p2.get_id, supply_point_id2, 10)
        set_default_consumption_for_supply_point(TEST_DOMAIN, p3.get_id, supply_point_id2, 10)
        set_default_consumption_for_supply_point(TEST_DOMAIN, p5.get_id, supply_point_id2, 10)

    @classmethod
    def tearDownClass(cls):
        delete_domain_phone_numbers(TEST_DOMAIN)
        CommCareUser.get_by_username('stella').delete()
        CommCareUser.get_by_username('super').delete()
        FacilityInCharge.objects.all().delete()
        delete_all_locations()
        LocationType.objects.all().delete()
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()
        SQLProduct.objects.all().delete()
        EWSGhanaConfig.for_domain(TEST_DOMAIN).delete()
        DocDomainMapping.objects.all().delete()
        generator.delete_all_subscriptions()
        cls.sms_backend_mapping.delete()
        cls.backend.delete()
        Domain.get_by_name(TEST_DOMAIN).delete()


def assign_products_to_location():
    ng = SQLProduct.objects.get(domain=TEST_DOMAIN, code='ng')
    jd = SQLProduct.objects.get(domain=TEST_DOMAIN, code='jd')
    mg = SQLProduct.objects.get(domain=TEST_DOMAIN, code='mg')
    location = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='garms')
    location.products = [ng, jd, mg]
    location.save()


def restore_location_products():
    location = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='garms')
    mg = SQLProduct.objects.get(domain=TEST_DOMAIN, code='mg')
    location.products = [mg]
    location.save()
