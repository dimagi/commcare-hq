from io import BytesIO
from tempfile import mkstemp

from django.test import Client, TestCase
from django.urls import reverse

from soil import BlobDownload
from soil.util import (
    expose_blob_download,
    expose_cached_download,
    expose_file_download,
)

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


class TestAuthenticatedDownloadBase(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAuthenticatedDownloadBase, cls).setUpClass()

        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.couch_user = WebUser.create(None, "test", "foobar", None, None)
        cls.couch_user.add_domain_membership(cls.domain, is_admin=True)
        cls.couch_user.save()

    def setUp(self):
        super(TestAuthenticatedDownloadBase, self).setUp()

        self.client = Client()
        self.client.login(username='test', password='foobar')

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()

        super(TestAuthenticatedDownloadBase, cls).tearDownClass()


class TestAuthenticatedCachedDownload(TestAuthenticatedDownloadBase):
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


class TestAuthenticatedFileDownload(TestAuthenticatedDownloadBase):
    @classmethod
    def setUpClass(cls):
        super(TestAuthenticatedFileDownload, cls).setUpClass()

        fd, cls.path = mkstemp()
        with open(fd, 'w') as f:
            f.write('content')

    def test_no_auth_needed(self):
        ref = expose_file_download(self.path, expiry=60)
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(next(response.streaming_content), b'content')

    def test_user_auth_required_access_allowed(self):
        ref = expose_file_download(self.path, expiry=60, owner_ids=[self.couch_user.get_id])
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(next(response.streaming_content), b'content')

        ref = expose_file_download(self.path, expiry=60, owner_ids=[self.couch_user.get_id], use_transfer=True)
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(next(response.streaming_content), b'content')

    def test_user_auth_required_access_denied(self):
        ref = expose_file_download(self.path, expiry=60, owner_ids=['foo'])
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(response.status_code, 403)

        ref = expose_file_download(self.path, expiry=60, owner_ids=['foo'], use_transfer=True)
        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(response.status_code, 403)


class TestAuthenticatedBlobDownload(TestAuthenticatedDownloadBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super().tearDownClass()

    def test_no_auth_needed(self):
        ref = expose_blob_download(
            'identifier',
            expiry=60,
            content_disposition='text/xml',
        )
        self.db.put(BytesIO(b'content'), meta=new_meta(key=ref.download_id))

        response = BlobDownload.get(ref.download_id).toHttpResponse()
        self.assertEqual(next(response.streaming_content), b'content')

    def test_user_auth_required_access_allowed(self):
        ref = expose_blob_download(
            'identifier',
            expiry=60,
            content_disposition='text/xml',
            owner_ids=[self.couch_user.get_id]
        )
        self.db.put(BytesIO(b'content'), meta=new_meta(key=ref.download_id))

        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(next(response.streaming_content), b'content')

    def test_user_auth_required_access_denied(self):
        ref = expose_blob_download(
            'identifier',
            expiry=60,
            content_disposition='text/xml',
            owner_ids=['foo']
        )
        self.db.put(BytesIO(b'content'), meta=new_meta(key=ref.download_id))

        response = self.client.get(reverse('retrieve_download', args=[ref.download_id]) + "?get_file")
        self.assertEqual(response.status_code, 403)
