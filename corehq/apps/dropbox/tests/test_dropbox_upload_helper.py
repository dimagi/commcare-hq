from django.test import TestCase

from ..models import DropboxUploadHelper
from ..exceptions import DropboxUploadAlreadyInProgress


class DropboxUploadHelperTest(TestCase):

    def test_successful_creation(self):
        kwargs = {
            'download_id': 'abc123',
            'src': 'commcare.zip',
            'dest': 'cc.zip'
        }
        helper = DropboxUploadHelper.create('my_bogus_token', **kwargs)

        self.assertEqual(helper.src, kwargs['src'])
        self.assertEqual(helper.dest, kwargs['dest'])
        self.assertEqual(helper.download_id, kwargs['download_id'])

    def test_upload_in_progress_creation(self):
        kwargs = {
            'download_id': 'abc123',
            'src': 'commcare.zip',
            'dest': 'cc.zip'
        }
        DropboxUploadHelper.create('my_bogus_token', **kwargs)

        with self.assertRaises(DropboxUploadAlreadyInProgress):
            DropboxUploadHelper.create('my_bogus_token', **kwargs)

    def test_successful_creation_after_failure(self):
        kwargs = {
            'download_id': 'abc123',
            'src': 'commcare.zip',
            'dest': 'cc.zip'
        }
        helper = DropboxUploadHelper.create('my_bogus_token', **kwargs)
        helper.failure_reason = 'Dumb reason'
        helper.save()

        try:
            DropboxUploadHelper.create('my_bogus_token', **kwargs)
        except Exception, e:
            self.fail(e)
