from __future__ import absolute_import
from __future__ import unicode_literals

import mock
from django.test import TestCase
from django.core.exceptions import ValidationError

from custom.icds.models import (
    HostedCCZLink,
    HostedCCZ,
)


@mock.patch('custom.icds.tasks.setup_ccz_file_for_hosting.delay')
class TestHostedCCZ(TestCase):
    def setUp(self):
        super(TestHostedCCZ, self).setUp()
        self.link = HostedCCZLink.objects.create(username="username", password="password",
                                                 identifier="link123", domain="test")
        self.hosted_ccz = HostedCCZ(link=self.link, app_id="dummy", version=12, profile_id="12345")

    def tearDown(self):
        self.link.delete()
        super(TestHostedCCZ, self).tearDown()

    @mock.patch('custom.icds.models.get_build_doc_by_version', return_value={'is_released': True, 'name': 'App'})
    def test_valid_hosted_ccz(self, *_):
        self.hosted_ccz.full_clean()

    def test_build_not_present(self, _):
        with self.assertRaisesMessage(ValidationError, "Build not found for app dummy and version 12."):
            self.hosted_ccz.full_clean()

    @mock.patch('custom.icds.models.get_build_doc_by_version', return_value={'is_released': False, 'name': 'App'})
    def test_released_version(self, *_):
        with self.assertRaisesMessage(ValidationError, "Version not released. Please mark it as released."):
            self.hosted_ccz.full_clean()

    def test_blob_id(self, _):
        self.assertEqual(self.hosted_ccz.blob_id, "dummy1212345")

    @mock.patch('custom.icds.models.get_build_doc_by_version', lambda *args: {'is_released': True, 'name': 'App'})
    def test_setup_ccz_file_for_hosting_on_save(self, setup_mock):
        self.hosted_ccz.save()
        setup_mock.assert_called_with(self.hosted_ccz.pk, user_email=None)
        self.hosted_ccz.delete()

    @mock.patch('custom.icds.models.get_build_doc_by_version', lambda *args: {'is_released': True, 'name': 'App'})
    def test_uniqueness(self, *_):
        self.hosted_ccz.save()
        error_message = "Hosted ccz with this Link, App id, Version and Profile id already exists."
        with self.assertRaisesMessage(ValidationError, error_message):
            HostedCCZ.objects.create(
                link=self.hosted_ccz.link,
                app_id=self.hosted_ccz.app_id,
                version=self.hosted_ccz.version,
                profile_id=self.hosted_ccz.profile_id,
            )
        self.hosted_ccz.delete()

    @mock.patch('custom.icds.models.HostedCCZUtility.remove_file_from_blobdb')
    @mock.patch('custom.icds.models.get_build_doc_by_version', lambda *args: {'is_released': True, 'name': 'App'})
    def test_delete_ccz(self, mock_delete, _):
        self.hosted_ccz.save()
        link2 = HostedCCZLink.objects.create(username="username", password="password",
                                             identifier="link1234", domain="test")
        hosted_ccz = HostedCCZ.objects.create(
            link=link2,
            app_id=self.hosted_ccz.app_id,
            version=self.hosted_ccz.version,
            profile_id=self.hosted_ccz.profile_id
        )
        self.assertEqual(self.hosted_ccz.blob_id, hosted_ccz.blob_id)

        self.hosted_ccz.delete()
        self.assertFalse(mock_delete.called)

        hosted_ccz.delete()
        self.assertTrue(mock_delete.called)
