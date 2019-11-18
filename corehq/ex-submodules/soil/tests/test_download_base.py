from io import BytesIO
from uuid import uuid4
from django.test import TestCase

from soil import BlobDownload
from soil.util import expose_blob_download

from corehq.blobs.tests.util import new_meta, TemporaryFilesystemBlobDB


class TestBlobDownload(TestCase):
    identifier = 'identifier'

    @classmethod
    def setUpClass(cls):
        super(TestBlobDownload, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestBlobDownload, cls).tearDownClass()

    def test_expose_blob_download(self):
        ref = expose_blob_download(
            self.identifier,
            expiry=60,
            content_disposition='text/xml',
        )
        self.db.put(BytesIO(b'content'), meta=new_meta(key=ref.download_id))

        response = BlobDownload.get(ref.download_id).toHttpResponse()
        self.assertEqual(next(response.streaming_content), b'content')
