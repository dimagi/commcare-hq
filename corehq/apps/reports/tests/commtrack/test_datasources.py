import uuid

from django.test import TestCase

from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import bootstrap_domain, make_loc, get_single_balance_block
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.reports.commtrack.data_sources import StockStatusDataSource
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.tests.utils import sharded


@sharded
class StockStatusDataSourceTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(StockStatusDataSourceTests, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.project = bootstrap_domain(cls.domain)
        cls.interface = SupplyInterface(cls.domain)

        cls.product = make_product(cls.domain, 'A Product', 'prodcode_a')
        cls.location = make_loc('1234', name='ben', domain=cls.domain)
        cls.location2 = make_loc('1235', name='ken', domain=cls.domain)
        cls.supply_point = cls.location.linked_supply_point()

        submit_case_blocks(
            [get_single_balance_block(cls.supply_point.case_id, cls.product._id, 50)],
            cls.domain
        )

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(StockStatusDataSourceTests, cls).tearDownClass()

    def test_stock_status_data_source_single_location(self):
        config = {
            'domain': self.domain,
            'location_id': self.location.location_id,
            'advanced_columns': True,
        }
        self.assertEqual(
            list(StockStatusDataSource(config).get_data()),
            [{
                'category': 'nodata',
                'consumption': None,
                'current_stock': 50,
                'location_id': self.location.location_id,
                'months_remaining': None,
                'product_id': self.product._id,
                'product_name': self.product.name,
                'resupply_quantity_needed': None
            }]
        )

    def test_stock_status_data_source_aggregate(self):
        config = {
            'domain': self.domain,
            'aggregate': True,
            'advanced_columns': True,
        }
        self.assertEqual(
            list(StockStatusDataSource(config).get_data()),
            [{
                'category': 'nodata',
                'consumption': None,
                'count': 1,
                'current_stock': 50,
                'location_id': None,
                'months_remaining': None,
                'product_id': self.product._id,
                'product_name': self.product.name,
                'resupply_quantity_needed': None
            }]
        )

    def test_stock_status_data_source_raw(self):
        ledger_value = LedgerAccessors(self.domain).get_ledger_value(
            self.supply_point.case_id, "stock", self.product._id
        )

        config = {
            'domain': self.domain,
            'aggregate': False,
            'advanced_columns': True,
        }
        self.assertEqual(
            list(StockStatusDataSource(config).get_data()),
            [{
                'category': 'nodata',
                'consumption': None,
                'current_stock': 50,
                'last_reported': ledger_value.last_modified,
                'location_id': self.location.location_id,
                'months_remaining': None,
                'product_id': self.product._id,
                'product_name': self.product.name,
                'resupply_quantity_needed': None}]
        )
