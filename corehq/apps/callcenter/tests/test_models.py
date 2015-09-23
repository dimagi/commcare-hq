from corehq.apps.callcenter.const import WEEK1, WEEK0, MONTH0
from corehq.apps.callcenter.models import TypedIndicator, ByTypeIndicator
from django.test import SimpleTestCase


class ModelTests(SimpleTestCase):
    def test_types_by_date_range(self):
        by_type = ByTypeIndicator(types=[
            TypedIndicator(active=True, date_ranges=[WEEK0, WEEK1], type='dog'),
            TypedIndicator(active=True, date_ranges=[WEEK0], type='cat'),
            TypedIndicator(active=True, date_ranges=[WEEK1], type='canary'),
            TypedIndicator(active=True, date_ranges=[WEEK1, MONTH0], type='fish'),
            TypedIndicator(active=False, date_ranges=[MONTH0], type='whale'),
        ])

        self.assertEqual(by_type.types_by_date_range(), {
            WEEK0: {'dog', 'cat'},
            WEEK1: {'dog', 'canary', 'fish'},
            MONTH0: {'fish'},
        })

