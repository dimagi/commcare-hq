from __future__ import unicode_literals
from __future__ import absolute_import
from builtins import range
from tempfile import NamedTemporaryFile
from unittest import TestCase

import corehq.blobs.util as mod


class TestClosingContextProxy(TestCase):

    def test_proxy_is_iterable(self):
        with NamedTemporaryFile() as tmp:
            tmp.write("line 1\nline 2\n")
            tmp.seek(0)
            proxy = mod.ClosingContextProxy(tmp)
            self.assertEqual(list(proxy), ["line 1\n", "line 2\n"])


class TestRandomUrlId(TestCase):

    sample_size = 100

    def setUp(self):
        self.ids = [mod.random_url_id(8) for x in range(self.sample_size)]

    def test_random_id_length(self):
        self.assertGreater(min(len(id) for id in self.ids), 0, self.ids)
        self.assertEqual(max(len(id) for id in self.ids), 11, self.ids)

    def test_random_id_randomness(self):
        self.assertEqual(len(set(self.ids)), self.sample_size, self.ids)
