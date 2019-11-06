from mock import Mock

from corehq.apps.api.resources import v0_5
from corehq.apps.api.tests.utils import APIResourceTest


class TestStockTransactionResource(APIResourceTest):
    resource = v0_5.StockTransactionResource
    api_name = 'v0.5'

    @classmethod
    def setUpClass(cls):
        super(TestStockTransactionResource, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestStockTransactionResource, cls).tearDownClass()

    def test_building_filters(self):
        date1 = 'start'
        date2 = 'end'
        api = v0_5.StockTransactionResource()
        filters = {'start_date': date1,
                   'end_date': date2}
        orm_filters = api.build_filters(filters=filters)
        self.assertEqual(orm_filters['report__date__gte'], date1)
        self.assertEqual(orm_filters['report__date__lte'], date2)

    def test_dehydrate(self):
        bm = self.create_hydrated_bundle()
        api = v0_5.StockTransactionResource()

        bundle = api.dehydrate(bm)
        self.assertEqual(bundle.data['product_name'], 'name')
        self.assertEqual(bundle.data['transaction_date'], 'date')

    @classmethod
    def create_hydrated_bundle(cls):
        bm = Mock()
        bm.data = {}
        bm.obj = Mock()
        bm.obj.sql_product = Mock()
        bm.obj.sql_product.name = 'name'
        bm.obj.report = Mock()
        bm.obj.report.date = 'date'
        return bm
