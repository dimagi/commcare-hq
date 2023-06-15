from datetime import datetime
from freezegun import freeze_time
from django.test import SimpleTestCase, override_settings
from corehq.apps.domain.models import Domain


class DomainTests(SimpleTestCase):
    def test_odata_feed_limit_returns_set_value(self):
        domain = Domain(odata_feed_limit=5)
        self.assertEqual(domain.get_odata_feed_limit(), 5)

    @override_settings(DEFAULT_ODATA_FEED_LIMIT=10)
    def test_odata_feed_limit_when_unset_uses_default(self):
        domain = Domain()
        self.assertEqual(domain.get_odata_feed_limit(), 10)

    @freeze_time('2023-06-05')
    def test_date_created_defaults_to_utcnow_when_not_specified(self):
        domain = Domain()
        self.assertEqual(domain.date_created, datetime(year=2023, month=6, day=5))

    def test_date_created_can_be_overridden_by_constructor(self):
        domain = Domain(date_created=datetime(year=2023, day=1, month=1))
        self.assertEqual(domain.date_created, datetime(year=2023, month=1, day=1))
