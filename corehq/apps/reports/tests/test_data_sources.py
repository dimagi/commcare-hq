from datetime import datetime

from django.test import TestCase
from django.test.utils import override_settings

from corehq.apps.commtrack.models import StockState
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.commtrack.data_sources import StockStatusDataSource, StockStatusDataSourceNew
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import LedgerValue
from corehq.form_processor.utils.general import should_use_sql_backend
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.helpers import make_product
from corehq.apps.commtrack.tests.util import make_loc


CURRENT_STOCK = StockStatusDataSource.SLUG_CURRENT_STOCK
PRODUCT_ID = StockStatusDataSource.SLUG_PRODUCT_ID
LOCATION_ID = StockStatusDataSource.SLUG_LOCATION_ID


TEST_DOMAIN = 'commtrack-test1'


class DataSourceTest(TestCase):
    data_source_class = StockStatusDataSource

    @classmethod
    def setUpClass(cls):
        cls.domain = create_domain(TEST_DOMAIN)
        cls.domain.convert_to_commtrack()
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
        ledger_values = []
        for region_name, districts in test_setup.items():
            region = make_loc(region_name, domain=TEST_DOMAIN, type='region')
            cls.regions[region_name] = region
            for district_name, sites in districts.items():
                district = make_loc(district_name, domain=TEST_DOMAIN, type='district', parent=region)
                cls.districts[district_name] = district
                for site_name, products in sites.items():
                    site = make_loc(site_name, type='site', parent=district, domain=TEST_DOMAIN)
                    cls.sites[site_name] = (site, products)
                    supply_point = site.linked_supply_point()
                    for p_code, stock in products.items():
                        prod = cls.products[p_code]
                        if should_use_sql_backend(TEST_DOMAIN):
                            ledger_values.append(LedgerValue(
                                domain=TEST_DOMAIN,
                                section_id='stock',
                                case_id=supply_point.case_id,
                                entry_id=prod._id,
                                balance=stock,
                                last_modified=datetime.utcnow(),
                                location_id=site._id,
                            ))
                        else:
                            StockState.objects.create(
                                section_id='stock',
                                case_id=supply_point.case_id,
                                product_id=prod._id,
                                stock_on_hand=stock,
                                last_modified_date=datetime.utcnow(),
                                sql_product=SQLProduct.objects.get(product_id=prod._id),
                                sql_location=site.sql_location
                            )

        if should_use_sql_backend(TEST_DOMAIN):
            from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
            LedgerAccessorSQL.save_ledger_values(ledger_values)

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.domain.delete()  # domain delete cascades to everything else

    def test_raw_cases(self):
        config = {
            'domain': TEST_DOMAIN,
            'enddate': datetime.utcnow()
        }
        data = list(self.data_source_class(config).get_data())
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
            'location_id': location,
            'enddate': datetime.utcnow()
        }
        data = list(self.data_source_class(config).get_data())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][LOCATION_ID], self.sites['A-b-1'][0]._id)
        self.assertEqual(data[0][PRODUCT_ID], self.products['pA']._id)
        self.assertEqual(data[0][CURRENT_STOCK], 2)

    def test_aggregate_level1(self):
        location = self.regions['A']._id
        config = {
            'domain': TEST_DOMAIN,
            'location_id': location,
            'aggregate': True,
            'enddate': datetime.utcnow()
        }
        data = list(self.data_source_class(config).get_data())
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
            'aggregate': True,
            'enddate': datetime.utcnow()
        }
        data = list(self.data_source_class(config).get_data())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][CURRENT_STOCK], 2)


class DataSourceTestSQL(DataSourceTest):
    data_source_class = StockStatusDataSourceNew

    @classmethod
    def setUpClass(cls):
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            super(DataSourceTestSQL, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True):
            super(DataSourceTestSQL, cls).tearDownClass()
