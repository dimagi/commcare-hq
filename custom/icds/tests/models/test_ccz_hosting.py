from __future__ import absolute_import
from __future__ import unicode_literals

import mock
from django.test import TestCase
from django.core.exceptions import ValidationError

from custom.icds.models import (
    CCZHostingLink,
    CCZHosting,
)


@mock.patch('custom.icds.tasks.setup_ccz_file_for_hosting.delay')
class TestCCZHosting(TestCase):
    def setUp(self):
        super(TestCCZHosting, self).setUp()
        self.link = CCZHostingLink.objects.create(username="username", password="password",
                                                  identifier="link123", domain="test")
        self.ccz_hosting = CCZHosting(link=self.link, app_id="dummy", version=12, profile_id="12345")

    def tearDown(self):
        self.link.delete()
        super(TestCCZHosting, self).tearDown()

    @mock.patch('custom.icds.models.get_build_by_version', return_value={'is_released': True, 'name': 'App'})
    def test_valid_ccz_hosting(self, *_):
        self.ccz_hosting.full_clean()

    def test_build_not_present(self, _):
        with self.assertRaisesMessage(ValidationError, "Build not found for app dummy and version 12."):
            self.ccz_hosting.full_clean()

    @mock.patch('custom.icds.models.get_build_by_version', return_value={'is_released': False, 'name': 'App'})
    def test_released_version(self, *_):
        with self.assertRaisesMessage(ValidationError, "Version not released. Please mark it as released."):
            self.ccz_hosting.full_clean()

    def test_blob_id(self, _):
        self.assertEqual(self.ccz_hosting.blob_id, "dummy1212345")

    @mock.patch('custom.icds.models.get_build_by_version', lambda *args: {'is_released': True, 'name': 'App'})
    def test_setup_ccz_file_for_hosting_on_save(self, setup_mock):
        self.ccz_hosting.save()
        setup_mock.assert_called_with(self.ccz_hosting.pk)
        self.ccz_hosting.delete()

    @mock.patch('custom.icds.models.get_build_by_version', lambda *args: {'is_released': True, 'name': 'App'})
    def test_uniqueness(self, *_):
        self.ccz_hosting.save()
        error_message = "Ccz hosting with this Link, App id, Version and Profile id already exists."
        with self.assertRaisesMessage(ValidationError, error_message):
            CCZHosting.objects.create(
                link=self.ccz_hosting.link,
                app_id=self.ccz_hosting.app_id,
                version=self.ccz_hosting.version,
                profile_id=self.ccz_hosting.profile_id,
            )
        self.ccz_hosting.delete()

    @mock.patch('custom.icds.models.CCZHostingUtility.remove_file_from_blobdb')
    @mock.patch('custom.icds.models.get_build_by_version', lambda *args: {'is_released': True, 'name': 'App'})
    def test_delete_ccz(self, mock_delete, _):
        self.ccz_hosting.save()
        link2 = CCZHostingLink.objects.create(username="username", password="password",
                                              identifier="link1234", domain="test")
        ccz_hosting = CCZHosting.objects.create(
            link=link2,
            app_id=self.ccz_hosting.app_id,
            version=self.ccz_hosting.version,
            profile_id=self.ccz_hosting.profile_id
        )
        self.assertEqual(self.ccz_hosting.blob_id, ccz_hosting.blob_id)

        self.ccz_hosting.delete()
        self.assertFalse(mock_delete.called)

        ccz_hosting.delete()
        self.assertTrue(mock_delete.called)
