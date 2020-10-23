import gzip
import io
from unittest import mock
from django.test import SimpleTestCase


class GZipFileTests(SimpleTestCase):
    def setUp(self):
        self.data = gzip.compress(b"Some Test Data")

    def test_existing_file_handle_is_not_closed_when_gzip_is_closed(self):
        existing_handle = io.BytesIO(self.data)
        gzip_file = gzip.GzipFile(fileobj=existing_handle)
        with gzip_file:
            pass

        self.assertTrue(gzip_file.closed)
        self.assertFalse(existing_handle.closed)

    def test_filename_closes_properly(self):
        existing_handle = io.BytesIO(self.data)
        mocked_open = mock.MagicMock(return_value=existing_handle)

        with mock.patch('builtins.open', mocked_open):
            gzip_file = gzip.GzipFile(filename='somefile')
            with gzip_file:
                pass

            self.assertTrue(gzip_file.closed)
            self.assertTrue(existing_handle.closed)
