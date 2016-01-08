from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.load_balance import load_balance
from django.test import SimpleTestCase


class LoadBalanceTestCase(SimpleTestCase):
    def test_load_balance(self):
        abcd = ['a', 'b', 'c', 'd']
        key = 'my-load-balancing-test-key'

        for i in range(3):
            self.assertEqual(load_balance(key, abcd), 'a')
            self.assertEqual(load_balance(key, abcd), 'b')
            self.assertEqual(load_balance(key, abcd), 'c')
            self.assertEqual(load_balance(key, abcd), 'd')

    def test_reset_key(self):
        key = 'my-load-balancing-reset-test-key'
        client = get_redis_client().client.get_client()
        client.set(key, 999998)

        load_balance(key, [1])
        self.assertEqual(int(client.get(key)), 999999)

        load_balance(key, [1])
        self.assertIsNone(client.get(key))

        load_balance(key, [1])
        self.assertEqual(int(client.get(key)), 1)
