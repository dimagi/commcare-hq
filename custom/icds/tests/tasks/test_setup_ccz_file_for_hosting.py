from __future__ import absolute_import
from __future__ import unicode_literals

import mock
from django.template.defaultfilters import linebreaksbr
from django.test import SimpleTestCase

from custom.icds.tasks import setup_ccz_file_for_hosting
from custom.icds.models import (
    HostedCCZ,
    HostedCCZLink,
)


@mock.patch('custom.icds.tasks.hosted_ccz.open')
@mock.patch('custom.icds.tasks.hosted_ccz.wrap_app')
@mock.patch('custom.icds.tasks.hosted_ccz.get_build_doc_by_version')
@mock.patch('custom.icds.tasks.hosted_ccz.create_files_for_ccz')
@mock.patch('custom.icds.tasks.hosted_ccz.HostedCCZ.objects.get')
@mock.patch('custom.icds.models.HostedCCZUtility')
class TestSetUpCCZFileForHosting(SimpleTestCase):
    def setUp(self):
        super(TestSetUpCCZFileForHosting, self).setUp()
        self.link = HostedCCZLink(username="username", password="password", identifier="link1234", domain="test")
        self.hosted_ccz = HostedCCZ(link=self.link, app_id="dummy", version=12, profile_id="123456")

    def test_hosting_not_present(self, mock_ccz_utility, mock_get, *_):
        mock_result = mock.MagicMock()
        mock_result.return_value = True
        mock_ccz_utility.return_value.file_exists = mock_result
        mock_get.side_effect = HostedCCZ.DoesNotExist
        setup_ccz_file_for_hosting(3)
        self.assertFalse(mock_result.called)

    def test_ccz_already_present(self, mock_ccz_utility, mock_get, mock_create_ccz, *_):
        mock_result = mock.MagicMock()
        mock_result.return_value = True
        mock_ccz_utility.return_value.file_exists = mock_result
        mock_get.return_value = self.hosted_ccz
        mock_result.return_value = True
        setup_ccz_file_for_hosting(3)
        self.assertTrue(mock_result.called)
        self.assertFalse(mock_create_ccz.called)

    def test_ccz_not_already_present(self, mock_ccz_utility, mock_get, mock_create_ccz, mock_get_build, *_):
        mock_get.return_value = self.hosted_ccz

        mock_result = mock.MagicMock()
        mock_result.return_value = False
        mock_ccz_utility.return_value.file_exists = mock_result

        setup_ccz_file_for_hosting(3)

        self.assertTrue(mock_result.called)
        mock_get_build.assert_called_with(self.hosted_ccz.domain, self.hosted_ccz.app_id,
                                          self.hosted_ccz.version)
        self.assertTrue(mock_create_ccz.called)
        self.assertTrue(mock_ccz_utility.return_value.store_file_in_blobdb.called)

    @mock.patch('custom.icds.tasks.hosted_ccz.send_html_email_async.delay')
    def test_ccz_creation_fails(self, mock_email, mock_ccz_utility, mock_get, mock_create_ccz, mock_get_build,
                                mock_wrapped_app, *_):
        mock_wrapped_app.return_value.name = "My App"
        mock_get.return_value = self.hosted_ccz

        mock_result = mock.MagicMock()
        mock_result.return_value = False
        mock_ccz_utility.return_value.file_exists = mock_result

        mock_delete_ccz = mock.MagicMock()
        self.hosted_ccz.delete_ccz = mock_delete_ccz
        mock_delete_ccz.return_value = True

        mock_store = mock.MagicMock()
        mock_ccz_utility.return_value.store_file_in_blobdb = mock_store
        mock_store.side_effect = Exception("Fail hard!")
        with self.assertRaisesMessage(Exception, "Fail hard!"):
            setup_ccz_file_for_hosting(3, user_email="batman@gotham.com")

        mock_get_build.assert_called_with(self.hosted_ccz.domain, self.hosted_ccz.app_id,
                                          self.hosted_ccz.version)
        self.assertTrue(mock_create_ccz.called)
        self.assertTrue(mock_ccz_utility.return_value.store_file_in_blobdb.called)
        self.assertTrue(mock_delete_ccz.called)
        content = "Hi,\n" \
                  "CCZ could not be created for the following request:\n" \
                  "App: {app}\n" \
                  "Version: {version}\n" \
                  "Profile: {profile}\n" \
                  "Link: {link}" \
                  "".format(app="My App", version=self.hosted_ccz.version, profile=None,
                            link=self.hosted_ccz.link.identifier)
        mock_email.assert_called_with(
            "CCZ Hosting setup failed for app My App in project test",
            "batman@gotham.com",
            linebreaksbr(content)
        )
