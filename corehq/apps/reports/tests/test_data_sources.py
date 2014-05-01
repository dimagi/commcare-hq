from datetime import datetime
from django import test as unittest
from corehq.apps.commtrack.models import StockState
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.commtrack.data_sources import StockStatusDataSource
from corehq.apps.users.models import WebUser
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.helpers import make_supply_point, make_product
from corehq.apps.commtrack.tests.util import make_loc


CURRENT_STOCK = StockStatusDataSource.SLUG_CURRENT_STOCK
PRODUCT_ID = StockStatusDataSource.SLUG_PRODUCT_ID
LOCATION_ID = StockStatusDataSource.SLUG_LOCATION_ID


format_string = "%Y-%m-%d"
TEST_DOMAIN = 'commtrack-test1'

class DataSourceTest(object):
    # fixme: need to make a test again
    @classmethod
    def setUpClass(cls):

        cls.domain = create_domain(TEST_DOMAIN)
        cls.couch_user = WebUser.create(None, "report_test", "foobar")
        cls.couch_user.add_domain_membership(TEST_DOMAIN, is_admin=True)
        cls.couch_user.save()

        cls.products = {
            'pA': make_product(TEST_DOMAIN, 'prod A', 'pA'),
            'pB': make_product(TEST_DOMAIN, 'prod B', 'pB')
        }

        test_setup = {
            'A': {
                'A-a': {
                    'A-a-1': {'pA': 4, 'pB': 0},
                    'A-a-2': {'pB': 3},
                },
                'A-b': {
                    'A-b-1': {'pA': 2}
                }
            },
            'B': {
                'B-a': {
                    'B-a-1': {'pA': 1, 'pB': 1}
                }
            }
        }

        cls.sites = {}
        cls.regions = {}
        cls.districts = {}
        for region_name, districts in test_setup.items():
            region = make_loc(region_name, type='region')
            cls.regions[region_name] = region
            for district_name, sites in districts.items():
                district = make_loc(district_name, type='district', parent=region)
                cls.districts[district_name] = district
                for site_name, products in sites.items():
                    site = make_loc(site_name, type='site', parent=district, domain=TEST_DOMAIN)
                    cls.sites[site_name] = (site, products)
                    supply_point = make_supply_point(TEST_DOMAIN, site)
                    for p_code, stock in products.items():
                        prod = cls.products[p_code]
                        StockState.objects.create(
                            section_id='stock',
                            case_id=supply_point._id,
                            product_id=prod._id,
                            stock_on_hand=stock,
                            last_modified_date=datetime.utcnow(),
                        )

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.domain.delete()  # domain delete cascades to everything else

    def test_raw_cases(self):
        config = {
            'domain': TEST_DOMAIN
        }
        data = list(StockStatusDataSource(config).get_data())
        self.assertEqual(len(data), 6)
        by_location = map_reduce(lambda row: [(row[LOCATION_ID],)], data=data, include_docs=True)

        for site, products in self.sites.values():
            site_id = site._id
            rows = by_location[site_id]
            by_product = dict((row[PRODUCT_ID], row) for row in rows)
            for code, level in products.items():
                product_id = self.products[code]._id
                self.assertEqual(by_product[product_id][CURRENT_STOCK], level)

    def test_raw_cases_location(self):
        location = self.districts['A-b']._id
        config = {
            'domain': TEST_DOMAIN,
            'location_id': location
        }
        data = list(StockStatusDataSource(config).get_data())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][LOCATION_ID], self.sites['A-b-1'][0]._id)
        self.assertEqual(data[0][PRODUCT_ID], self.products['pA']._id)
        self.assertEqual(data[0][CURRENT_STOCK], 2)

    def test_aggregate_level1(self):
        location = self.regions['A']._id
        config = {
            'domain': TEST_DOMAIN,
            'location_id': location,
            'aggregate': True
        }
        data = list(StockStatusDataSource(config).get_data())
        self.assertEqual(len(data), 2)
        by_product = dict((row[PRODUCT_ID], row) for row in data)
        pA_id = self.products['pA']._id
        pB_id = self.products['pB']._id

        self.assertEqual(by_product[pA_id][CURRENT_STOCK], 6)
        self.assertEqual(by_product[pB_id][CURRENT_STOCK], 3)

    def test_aggregate_level2(self):
        location = self.districts['A-b']._id
        config = {
            'domain': TEST_DOMAIN,
            'location_id': location,
            'aggregate': True
        }
        data = list(StockStatusDataSource(config).get_data())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][CURRENT_STOCK], 2)
