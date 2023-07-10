import json
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.domain.models import Domain
from corehq.apps.export.const import SharingOption
from corehq.apps.export.dbaccessors import (
    delete_all_export_instances,
    get_form_exports_by_domain,
)
from corehq.apps.export.views.list import FormExportListHelper
from corehq.apps.export.views.new import CreateNewCustomFormExportView
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import privilege_enabled


class ViewTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ViewTestCase, cls).setUpClass()
        cls.domain = Domain(name="donkeykong", is_active=True)
        cls.domain.save()

        cls.username = 'bananafana'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, None, None)
        cls.user.set_role(cls.domain.name, 'admin')
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super(ViewTestCase, cls).tearDownClass()

    def setUp(self):
        self.client.login(username=self.username, password=self.password)


class ExportListHelperSharingStatusTest(ViewTestCase):
    def setUp(self):
        super().setUp()
        username = 'messi'
        password = '*******'
        self.other_user = WebUser.create(self.domain.name, username, password, None, None)
        self.other_user.set_role(self.domain.name, 'admin')
        self.other_user.save()
        self.request_factory = RequestFactory()

    def tearDown(self):
        self.other_user.delete(self.domain.name, deleted_by=None)
        delete_all_export_instances()

    def create_export(self, sharing_option, export_owner_id):
        export_post_data = json.dumps({
            "doc_type": "FormExportInstance",
            "domain": self.domain.name,
            "xmlns": "http://openrosa.org/formdesigner/237B85C0-78B1-4034-8277-5D37E3EA7FD1",
            "last_updated": None,
            "legacy_saved_export_schema_id": None,
            "is_daily_saved_export": False,
            "tables": [],
            "transform_dates": True,
            "last_accessed": None,
            "app_id": "6a48b8838d06febeeabb28c8c9516ab6",
            "is_deidentified": False,
            "split_multiselects": False,
            "external_blobs": {},
            "export_format": "csv",
            "include_errors": False,
            "type": "form",
            "name": "A Villager's Health > Registration > Reg form: 2016-06-27",
            "sharing": sharing_option,
            "owner_id": export_owner_id
        })
        resp = self.client.post(
            reverse(CreateNewCustomFormExportView.urlname, args=[self.domain.name]),
            export_post_data,
            content_type="application/json",
            follow=True
        )
        self.assertEqual(resp.status_code, 200)
        exports = get_form_exports_by_domain(self.domain.name)
        self.assertEqual(len(exports), 1)

    def assert_export_list_obey_its_sharing_status(
        self,
        sharing_option,
        request_user,
        return_request_user_exports,
        export_owner,
        expected_exports_count,
        expected_edit_status
    ):
        # Export belongs to export_owner
        self.create_export(sharing_option=sharing_option, export_owner_id=export_owner.userID)

        # User `request_user` is making the request
        request = self.request_factory.get(reverse('get_exports_page', args=[self.domain.name]))
        request.domain = self.domain.name
        request.couch_user = request_user

        helper = FormExportListHelper(request)
        exports_list, _total = helper.get_exports_page(page=1, limit=5, my_exports=return_request_user_exports)
        # We can check the total count, but this filter is for extra measure
        exports = list(filter(lambda export: export['owner_username'] == export_owner.username, exports_list))
        self.assertTrue(len(exports) == expected_exports_count)

        for export in exports:
            self.assertEqual(export['can_edit'], expected_edit_status)

    @patch('corehq.apps.reports.display._FormType.get_label_from_app', return_value='label')
    def test_export_sharing_is_edit_and_export(self, *args):
        """For EDIT_AND_EXPORT exports, other users should be able to see and edit it"""
        self.assert_export_list_obey_its_sharing_status(
            sharing_option=SharingOption.EDIT_AND_EXPORT,
            request_user=self.user,
            return_request_user_exports=False,
            export_owner=self.other_user,
            expected_exports_count=1,
            expected_edit_status=True
        )

    @patch('corehq.apps.reports.display._FormType.get_label_from_app', return_value='label')
    def test_export_sharing_is_export_only(self, *args):
        """For EXPORT_ONLY exports, other users should be able to see this export and not be able to edit it"""
        self.assert_export_list_obey_its_sharing_status(
            sharing_option=SharingOption.EXPORT_ONLY,
            request_user=self.user,
            return_request_user_exports=False,
            export_owner=self.other_user,
            expected_exports_count=1,
            expected_edit_status=False
        )

    @privilege_enabled(privileges.EXPORT_OWNERSHIP)
    @patch('corehq.apps.reports.display._FormType.get_label_from_app', return_value='label')
    def test_export_sharing_is_private(self, *args):
        """For PRIVATE exports, other users should not be able to see it.

        NOTE: Why is EXPORT_OWNERSHIP required only at this test you wonder? This privilege is restrictive. The
        behavior for exports on domains without this privilege is that they can be viewed and edited by others
        """
        self.assert_export_list_obey_its_sharing_status(
            sharing_option=SharingOption.PRIVATE,
            request_user=self.user,
            return_request_user_exports=False,
            export_owner=self.other_user,
            expected_exports_count=0,
            expected_edit_status=False
        )

    @privilege_enabled(privileges.EXPORT_OWNERSHIP)
    @patch('corehq.apps.reports.display._FormType.get_label_from_app', return_value='label')
    def test_owner_can_see_own_exports(self, *args):
        """
        The the owner of the export should be able to see and edit it when it's PRIVATE
        """
        self.assert_export_list_obey_its_sharing_status(
            sharing_option=SharingOption.PRIVATE,
            request_user=self.user,
            return_request_user_exports=True,
            export_owner=self.user,
            expected_exports_count=1,
            expected_edit_status=True
        )
