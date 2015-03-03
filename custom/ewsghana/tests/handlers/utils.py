import datetime
from couchdbkit.exceptions import ResourceNotFound
from couchforms.models import XFormInstance
from decimal import Decimal
from corehq import Domain
from corehq.apps.accounting import generator
from corehq.apps.commtrack.models import CommtrackConfig, CommtrackActionConfig, StockState
from corehq.apps.commtrack.tests.util import TEST_BACKEND, make_loc
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.sms.backend import test
from corehq.apps.sms.mixin import MobileBackend
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.utils import prepare_domain, bootstrap_user
from custom.logistics.test.test_script import TestScript
from casexml.apps.stock.models import StockReport, StockTransaction
from casexml.apps.stock.models import DocDomainMapping

TEST_DOMAIN = 'ewsghana-test'


class EWSScriptTest(TestScript):

    def _create_stock_state(self, product, factor):
        xform = XFormInstance.get('test-xform')
        loc = Location.by_site_code(TEST_DOMAIN, 'garms')
        for idx, i in enumerate([30, 6, 0]):
            report = StockReport(
                form_id=xform._id,
                date=datetime.datetime.now() - datetime.timedelta(days=i),
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
                stock_on_hand=40 - factor * (idx + 1),
                report=report
            )
            stock_transaction.save()

    def setUp(self):
        p1 = Product.get_by_code(TEST_DOMAIN, 'mc')
        p2 = Product.get_by_code(TEST_DOMAIN, 'lf')
        p3 = Product.get_by_code(TEST_DOMAIN, 'mg')
        self._create_stock_state(p1, 5)
        self._create_stock_state(p2, 10)
        self._create_stock_state(p3, 5)

    def tearDown(self):
        StockTransaction.objects.all().delete()
        StockReport.objects.all().delete()
        StockState.objects.all().delete()

    @classmethod
    def setUpClass(cls):
        domain = prepare_domain(TEST_DOMAIN)
        loc = make_loc(code="garms", name="Test RMS", type="Regional Medical Store", domain=domain.name)
        test.bootstrap(TEST_BACKEND, to_console=True)
        bootstrap_user(username='stella', domain=domain.name, home_loc=loc)
        bootstrap_user(username='super', domain=domain.name, home_loc=loc,
                       phone_number='222222', user_data={'role': 'In Charge'})

        try:
            XFormInstance.get(docid='test-xform')
        except ResourceNotFound:
            xform = XFormInstance(_id='test-xform')
            xform.save()
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

        config = CommtrackConfig.for_domain(domain.name)
        config.actions.append(
            CommtrackActionConfig(
                action='receipts',
                keyword='rec',
                caption='receipts'
            )
        )
        config.save()

    @classmethod
    def tearDownClass(cls):
        MobileBackend.load_by_name(TEST_DOMAIN, TEST_BACKEND).delete()
        CommCareUser.get_by_username('stella').delete()
        CommCareUser.get_by_username('super').delete()
        SQLLocation.objects.all().delete()
        for product in Product.by_domain(TEST_DOMAIN):
            product.delete()
        SQLProduct.objects.all().delete()
        EWSGhanaConfig.for_domain(TEST_DOMAIN).delete()
        DocDomainMapping.objects.all().delete()
        Location.by_site_code(TEST_DOMAIN, 'garms').delete()
        SQLLocation.objects.all().delete()
        generator.delete_all_subscriptions()
        Domain.get_by_name(TEST_DOMAIN).delete()
