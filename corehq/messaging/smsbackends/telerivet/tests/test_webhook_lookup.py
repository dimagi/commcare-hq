from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from django.test import TestCase


class TelerivetWebhookLookupTestCase(TestCase):
    def setUp(self):
        self.backend1 = SQLTelerivetBackend(
            name='TELERIVET1',
            is_global=True,
            hq_api_id=SQLTelerivetBackend.get_api_id()
        )
        self.backend1.set_extra_fields(
            webhook_secret='abc'
        )
        self.backend1.save()

        self.backend2 = SQLTelerivetBackend(
            name='TELERIVET2',
            is_global=True,
            hq_api_id=SQLTelerivetBackend.get_api_id()
        )
        self.backend2.set_extra_fields(
            webhook_secret='def'
        )
        self.backend2.save()

    def tearDown(self):
        self.backend1.delete()
        self.backend2.delete()

    def test_webhook_lookup(self):
        self.assertEqual(
            SQLTelerivetBackend.by_webhook_secret('abc'),
            self.backend1
        )

        self.assertEqual(
            SQLTelerivetBackend.by_webhook_secret('def'),
            self.backend2
        )

        self.assertIsNone(SQLTelerivetBackend.by_webhook_secret('ghi'))
