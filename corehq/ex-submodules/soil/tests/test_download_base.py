from io import StringIO
from django.test import SimpleTestCase

from soil import BlobDownload
from soil.util import expose_blob_download

from corehq.blobs.tests.util import TemporaryFilesystemBlobDB


class TestBlobDownload(SimpleTestCase):
    identifier = 'identifier'

    @classmethod
    def setUpClass(cls):
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_expose_blob_download(self):
        content_disposition = 'text/xml'
        download_id = 'abc123'

        self.db.put(StringIO(u'content'), self.identifier)

        expose_blob_download(
            self.identifier,
            content_disposition=content_disposition,
            download_id=download_id
        )

        download = BlobDownload.get(download_id)

        self.assertIsNotNone(download)

        response = download.toHttpResponse()
        self.assertEqual(response.streaming_content.next(), u'content')
