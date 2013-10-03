import datetime
from django.test import TestCase
from corehq.apps.commtrack.models import StockTransaction


class WrappingTest(TestCase):
    def test_stock_transaction(self):
        stock_transaction = StockTransaction.force_wrap({
            "action": "consumption",
            "product_entry": "9d14b21ab5ae6fb39d00d575c54d406b",
            "product": "a660733caacc170577445d13755b3be0",
            "@inferred": "true",
            "value": "5",
            "location_id": "6da439e2eb717e6b80a2d871956273f9",
            "received_on": "2013-01-11T00:00:00Z"
        })

        result = {
            "action": "consumption",
            "product_entry": "9d14b21ab5ae6fb39d00d575c54d406b",
            "product": "a660733caacc170577445d13755b3be0",
            "inferred": True,
            "value": 5,
            "location_id": "6da439e2eb717e6b80a2d871956273f9",
            "received_on": datetime.datetime(2013, 01, 11, 00, 00, 00),
        }

        for key, value in result.items():
            self.assertEqual(getattr(stock_transaction, key), value)
