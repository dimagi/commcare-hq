from __future__ import unicode_literals
from __future__ import absolute_import
from io import BytesIO

from django.test import TestCase

from corehq.blobs.tests.util import new_meta, TemporaryFilesystemBlobDB
from corehq.util.test_utils import generate_cases


class TestBlobMeta(TestCase):

    pass


@generate_cases([
    ("image/gif", True),
    ("image/jpeg", True),
    ("image/png", True),
    ("text/plain", False),
    ("application/octet-stream", False),
], TestBlobMeta)
def test_is_image(self, content_type, result):
    meta = new_meta(content_type=content_type)
    self.assertEqual(meta.is_image, result)
