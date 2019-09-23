from unittest import TestCase

import corehq.blobs.util as mod


class TestRandomUrlId(TestCase):

    sample_size = 100

    def setUp(self):
        self.ids = [mod.random_url_id(8) for x in range(self.sample_size)]

    def test_random_id_length(self):
        self.assertGreater(min(len(id) for id in self.ids), 0, self.ids)
        self.assertEqual(max(len(id) for id in self.ids), 11, self.ids)

    def test_random_id_randomness(self):
        self.assertEqual(len(set(self.ids)), self.sample_size, self.ids)
