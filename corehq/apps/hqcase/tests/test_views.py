import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.util.test_utils import (
    disable_quickcache,
    flag_enabled,
    privilege_enabled,
)


@sharded
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
@flag_enabled("API_THROTTLE_WHITELIST")
@patch("corehq.apps.hqcase.api.updates.validate_update_permission", MagicMock())
class TestCaseUpdateView(TestCase):
    """
    Test case update views for POST and PUT endpoints.
    (UPSERT logic for POST has been moved to PUT /ext/<external_id>/ endpoint.)
    """
    domain = "test-case-update"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        role = UserRole.create(
            cls.domain,
            "edit-data",
            permissions=HqPermissions(edit_data=True, access_api=True),
        )
        cls.web_user = WebUser.create(
            cls.domain, "testuser", "password", None, None, role_id=role.get_id
        )

    def setUp(self):
        self.client.login(username="testuser", password="password")

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        FormProcessorTestUtils.delete_all_xforms(self.domain)

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @patch("corehq.apps.hqcase.views.handle_case_update")
    def test_post_without_external_id(self, mock_handle_update):
        mock_handle_update.return_value = self._get_update_return()

        with patch(
            "corehq.apps.hqcase.views.serialize_case",
            return_value={"case_id": "new-case"},
        ):
            response = self.client.post(
                reverse("case_api", args=(self.domain,)),
                json.dumps(
                    {
                        "case_type": "patient",
                        "case_name": "Jane Doe",
                    }
                ),
                content_type="application/json",
                HTTP_USER_AGENT="test-agent",
            )

        self.assertEqual(response.status_code, 200)
        # Verify handle_case_update was called with is_creation=True
        mock_handle_update.assert_called_once()
        call_kwargs = mock_handle_update.call_args[1]
        self.assertTrue(call_kwargs["is_creation"])

    @patch("corehq.apps.hqcase.views.handle_case_update")
    def test_put_with_case_id_not_affected_by_external_id_logic(
        self, mock_handle_update
    ):
        mock_handle_update.return_value = self._get_update_return()

        with patch(
            "corehq.apps.hqcase.views.serialize_case",
            return_value={"case_id": "case-123"},
        ):
            response = self.client.put(
                f"/a/{self.domain}/api/case/v2/case-123/",
                json.dumps(
                    {
                        "case_name": "Updated Name",
                        "external_id": "ext-456",
                    }
                ),
                content_type="application/json",
                HTTP_USER_AGENT="test-agent",
            )

        self.assertEqual(response.status_code, 200)
        # Verify handle_case_update was called with is_creation=False
        mock_handle_update.assert_called_once()
        call_kwargs = mock_handle_update.call_args[1]
        self.assertFalse(call_kwargs["is_creation"])

    @staticmethod
    def _get_update_return():
        mock_xform = MagicMock(spec=XFormInstance)
        mock_xform.form_id = "test-form-id"
        mock_case = MagicMock(spec=CommCareCase)
        return mock_xform, mock_case
