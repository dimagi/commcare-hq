import datetime
from uuid import uuid4

from django.db.models.signals import post_save
from django.test import TestCase

from corehq.apps.commtrack.models import StockState, update_domain_mapping
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.products.models import SQLProduct

from corehq.apps.reports.commtrack import LedgersByLocationDataSource


class TestLedgersByLocation(TestCase):
    @classmethod
    def setUpClass(cls):
        def make_stock_state(location, product, soh, section_id='stock'):
            return StockState.objects.create(
                section_id=section_id,
                sql_location=location,
                case_id=uuid4().hex,
                sql_product=product,
                product_id=product.product_id,
                stock_on_hand=soh,
                last_modified_date=datetime.datetime.now(),
            )

        def make_product(name):
            return SQLProduct.objects.create(domain='test', name=name,
                                             product_id=uuid4().hex)

        def make_location(name):
            return make_loc(name, domain='test').sql_location

        # turn off the StockState post_save signal handler
        post_save.disconnect(update_domain_mapping, StockState)

        cls.aspirin = make_product(name="Aspirin")
        cls.bandaids = make_product(name="Bandaids")

        cls.boston = make_location("Boston")
        make_stock_state(cls.boston, cls.aspirin, 135)
        make_stock_state(cls.boston, cls.bandaids, 43)
        make_stock_state(cls.boston, cls.aspirin, 82, section_id='foo')

        cls.cambridge = make_location("Cambridge")
        make_stock_state(cls.cambridge, cls.aspirin, 414)
        make_stock_state(cls.cambridge, cls.bandaids, 107)

        cls.allston = make_location(name="Allston")

    @classmethod
    def tearDownClass(cls):
        delete_all_locations()

    def test_show_all_rows_ordered(self):
        report = LedgersByLocationDataSource(
            domain='test',
            section_id='stock'
        )
        self.assertEqual(
            [row.location.name for row in report.location_ledgers],
            [self.allston.name, self.boston.name, self.cambridge.name]
        )

    def test_one_row(self):
        report = LedgersByLocationDataSource(
            domain='test',
            section_id='stock'
        )
        boston = [row for row in report.location_ledgers if row.location.name == "Boston"][0]
        self.assertEqual(boston.stock[self.aspirin.product_id], 135)
        self.assertEqual(boston.stock[self.bandaids.product_id], 43)

    def test_another_ledger_section(self):
        report = LedgersByLocationDataSource(
            domain='test',
            section_id='foo'
        )
        for row in report.location_ledgers:
            if row.location.name == "Boston":
                self.assertEqual(row.stock[self.aspirin.product_id], 82)
            else:
                self.assertNotIn(self.aspirin.product_id, row.stock)
