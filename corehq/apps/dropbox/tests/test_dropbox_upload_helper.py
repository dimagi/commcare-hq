from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch, MagicMock
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..models import DropboxUploadHelper
from ..exceptions import DropboxUploadAlreadyInProgress


@patch('corehq.apps.dropbox.models.DropboxUploadHelper._ensure_valid_token', MagicMock())
class DropboxUploadHelperTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(DropboxUploadHelperTest, cls).setUpClass()
        cls.domain = create_domain('adomain')
        cls.user = WebUser.create('adomain', 'ben', '***')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()
        super(DropboxUploadHelperTest, cls).tearDownClass()

    def test_successful_creation(self):
        kwargs = {
            'download_id': 'abc123',
            'src': 'commcare.zip',
            'dest': 'cc.zip',
            'user': self.user.get_django_user(),
        }
        helper = DropboxUploadHelper.create('my_bogus_token', **kwargs)

        self.assertEqual(helper.src, kwargs['src'])
        self.assertEqual(helper.dest, kwargs['dest'])
        self.assertEqual(helper.download_id, kwargs['download_id'])

    def test_upload_in_progress_creation(self):
        kwargs = {
            'download_id': 'abc123',
            'src': 'commcare.zip',
            'dest': 'cc.zip',
            'user': self.user.get_django_user(),
        }
        DropboxUploadHelper.create('my_bogus_token', **kwargs)

        with self.assertRaises(DropboxUploadAlreadyInProgress):
            DropboxUploadHelper.create('my_bogus_token', **kwargs)

    def test_successful_creation_after_failure(self):
        kwargs = {
            'download_id': 'abc123',
            'src': 'commcare.zip',
            'dest': 'cc.zip',
            'user': self.user.get_django_user(),
        }
        helper = DropboxUploadHelper.create('my_bogus_token', **kwargs)
        helper.failure_reason = 'Dumb reason'
        helper.save()

        try:
            DropboxUploadHelper.create('my_bogus_token', **kwargs)
        except Exception as e:
            self.fail(e)
