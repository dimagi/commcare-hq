import gzip
import os
import tempfile
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


class TestGzipCompressReadStream(TestCase):

    def _is_gzip_compressed(self, file_):
        with gzip.open(file_, 'r') as f:
            try:
                f.read(1)
                return True
            except OSError:
                return False

    def test_compression(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"x")
            compress_stream = mod.GzipCompressReadStream(f)
            with tempfile.NamedTemporaryFile() as compressed_f:
                compressed_f.write(compress_stream.read())
                self.assertTrue(self._is_gzip_compressed(compressed_f))

    def test_content_length(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"x")
            compress_stream = mod.GzipCompressReadStream(f)
            with self.assertRaises(Exception):
                compress_stream.content_length
            content_length = len(compress_stream.read())
            self.assertEqual(compress_stream.content_length, content_length)

