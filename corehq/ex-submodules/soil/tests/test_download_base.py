from io import BytesIO

from django.test import Client, TestCase
from django.urls import reverse

from soil import BlobDownload
from soil.util import expose_blob_download, expose_cached_download

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, new_meta


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


class TestAuthenticatedDownload(TestCase):
    def setUp(self):
        super(TestAuthenticatedDownload, self).setUp()
        self.domain = 'test-domain'
        self.domain_obj = create_domain(self.domain)
        self.couch_user = WebUser.create(None, "test", "foobar", None, None)
        self.couch_user.add_domain_membership(self.domain, is_admin=True)
        self.couch_user.save()
        self.client = Client()
        self.client.login(username='test', password='foobar')

    def tearDown(self):
        self.couch_user.delete(deleted_by=None)
        self.domain_obj.delete()
        super(TestAuthenticatedDownload, self).tearDown()

    def test_no_auth_needed(self):
        ref = expose_cached_download(
            BytesIO(b'content'),
            expiry=60,
            file_extension='txt'
        )
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(response.content, b'content')

    def test_user_auth_required_access_allowed(self):
        ref = expose_cached_download(
            BytesIO(b'content'),
            expiry=60,
            file_extension='txt',
            owner_ids=[self.couch_user.get_id],
        )
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(response.content, b'content')

    def test_user_auth_required_access_denied(self):
        ref = expose_cached_download(
            BytesIO(b'content'),
            expiry=60,
            file_extension='txt',
            owner_ids=['foo'],
        )
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(response.status_code, 403)
