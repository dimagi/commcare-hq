from collections import defaultdict
import uuid
from django.test import SimpleTestCase
from corehq.toggles import deterministic_random


class DeterministicRandomTestCase(SimpleTestCase):

    def _random_string(self):
        return uuid.uuid4().hex

    def _random_strings(self, count):
        return [self._random_string() for i in range(count)]

    def test_random_strings(self):
        seen = set()
        for rand in self._random_strings(100):
            self.assertTrue(rand not in seen)
            seen.add(rand)
        self.assertEqual(100, len(seen))

    def test_consistency(self):
        seen = set()
        for seed in self._random_strings(100):
            converted_rand = deterministic_random(seed)
            self.assertTrue(0 <= converted_rand < 1)
            self.assertEqual(converted_rand, deterministic_random(seed))
            self.assertTrue(converted_rand not in seen)
            seen.add(converted_rand)

    def test_unicode(self):
        unicode_string = 'टूटना{}'.format(self._random_string())
        value = deterministic_random(unicode_string)
        self.assertEqual(value, deterministic_random(unicode_string))

    def test_randomness(self):
        buckets = defaultdict(lambda: 0)
        for i in range(10000):
            # use similar looking strings to make sure randomness is in the called function.
            # note that this also makes this (statistically-determined) test deterministic which is nice
            seed = 'test-string-{}'.format(i)
            converted_rand = deterministic_random(seed)
            self.assertTrue(0 <= converted_rand < 1)
            first_decimal = int("{:.1f}".format(converted_rand)[-1])
            buckets[first_decimal] += 1

        self.assertEqual(10, len(buckets))
        for i in range(10):
            # we expect about 1000 in each bucket and the sample is big enough that
            # these constraints are fine.
            self.assertTrue(900 < buckets[i] < 1100)
