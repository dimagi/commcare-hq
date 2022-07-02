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
