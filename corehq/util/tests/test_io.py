from __future__ import absolute_import
from __future__ import unicode_literals

from tempfile import NamedTemporaryFile
from unittest import TestCase

import corehq.util.io


class TestClosingContextProxy(TestCase):

    def test_proxy_is_iterable(self):
        with NamedTemporaryFile(mode='w+') as tmp:
            tmp.write("line 1\nline 2\n")
            tmp.seek(0)
            proxy = corehq.util.io.ClosingContextProxy(tmp)
            self.assertEqual(list(proxy), ["line 1\n", "line 2\n"])
