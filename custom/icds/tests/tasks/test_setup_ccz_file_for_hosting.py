from __future__ import absolute_import
from __future__ import unicode_literals

import mock
from django.test import SimpleTestCase

from custom.icds.tasks import setup_ccz_file_for_hosting
from custom.icds.models import (
    CCZHosting,
    CCZHostingLink,
)


@mock.patch('custom.icds.tasks.ccz_hosting.wrap_app')
@mock.patch('custom.icds.tasks.ccz_hosting.get_build_by_version')
@mock.patch('custom.icds.tasks.ccz_hosting.create_ccz_files')
@mock.patch('custom.icds.tasks.ccz_hosting.CCZHosting.objects.get')
@mock.patch('custom.icds.tasks.ccz_hosting.IcdsFile')
class TestSetUpCCZFileForHosting(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestSetUpCCZFileForHosting, cls).setUpClass()
        cls.link = CCZHostingLink(username="username", password="password", identifier="link1234", domain="test")
        cls.ccz_hosting = CCZHosting(link=cls.link, app_id="dummy", version=12, profile_id="123456")

    def test_hosting_not_present(self, mock_icds_file, mock_get, *_):
        mock_filter = mock.MagicMock()
        mock_icds_file.objects.filter = mock_filter
        mock_get.side_effect = CCZHosting.DoesNotExist
        setup_ccz_file_for_hosting(3)
        self.assertFalse(mock_filter.called)

    def test_ccz_already_present(self, mock_icds_file, mock_get, mock_create_ccz, *_):
        mock_filter = mock.MagicMock()
        mock_icds_file.objects.filter = mock_filter
        mock_get.return_value = self.ccz_hosting
        mock_filter.return_value.exists.return_value = True
        setup_ccz_file_for_hosting(3)
        self.assertTrue(mock_filter.called)
        self.assertFalse(mock_create_ccz.called)

    def test_ccz_not_already_present(self, mock_icds_file, mock_get, mock_create_ccz, mock_get_build, *_):
        mock_get.return_value = self.ccz_hosting

        mock_filter = mock.Mock()
        mock_icds_file.objects.filter = mock_filter
        mock_filter.return_value.exists.return_value = False

        setup_ccz_file_for_hosting(3)

        self.assertTrue(mock_filter.called)
        mock_get_build.assert_called_with(self.ccz_hosting.link.domain, self.ccz_hosting.app_id,
                                          self.ccz_hosting.version)
        self.assertTrue(mock_create_ccz.called)
        self.assertTrue(mock_icds_file.return_value.store_file_in_blobdb.called)
        self.assertTrue(mock_icds_file.return_value.save.called)
