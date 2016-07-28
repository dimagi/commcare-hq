from __future__ import unicode_literals
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
