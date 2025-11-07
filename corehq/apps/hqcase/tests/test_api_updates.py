from unittest.mock import MagicMock, patch

from django.test import TestCase

import pytest

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded

from ..api.core import UserError
from ..api.updates import _get_bulk_updates


@sharded
class TestBulkUpdatesUpsert(TestCase):
    """
    Tests for the upsert functionality on external_id in
    ``_get_bulk_updates()``, which allows bulk updates without a
    'create' flag to upsert on external_id if one is provided.
    """

    domain = "test-bulk-upsert"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.web_user = WebUser.create(
            cls.domain, "testuser", "password", None, None
        )

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        FormProcessorTestUtils.delete_all_xforms(self.domain)

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_with_external_id_no_existing_case_creates(
        self, mock_get_by_external_id
    ):
        mock_get_by_external_id.return_value = None

        data = [
            {
                "case_type": "patient",
                "case_name": "John Doe",
                "external_id": "ext-123",
                "owner_id": "test-owner",
            }
        ]

        updates = _get_bulk_updates(self.domain, data, self.web_user)

        assert len(updates) == 1
        assert updates[0]._is_case_creation
        assert updates[0].external_id == "ext-123"
        mock_get_by_external_id.assert_called_once_with(
            self.domain, "ext-123", raise_multiple=True
        )

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_with_external_id_existing_case_updates(
        self, mock_get_by_external_id
    ):
        existing_case = MagicMock(spec=CommCareCase)
        existing_case.case_id = "existing-case-id"
        mock_get_by_external_id.return_value = existing_case

        data = [
            {
                "case_name": "John Doe Updated",
                "external_id": "ext-123",
            }
        ]

        updates = _get_bulk_updates(self.domain, data, self.web_user)

        assert len(updates) == 1
        assert not updates[0]._is_case_creation
        assert updates[0].case_id == "existing-case-id"
        assert updates[0].external_id == "ext-123"
        mock_get_by_external_id.assert_called_once_with(
            self.domain, "ext-123", raise_multiple=True
        )

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_with_external_id_multiple_cases_raises_error(
        self, mock_get_by_external_id
    ):
        mock_get_by_external_id.side_effect = (
            CommCareCase.MultipleObjectsReturned(
                "Multiple cases found with external_id ext-123"
            )
        )

        data = [
            {
                "case_type": "patient",
                "case_name": "John Doe",
                "external_id": "ext-123",
                "owner_id": "test-owner",
            }
        ]

        with pytest.raises(CommCareCase.MultipleObjectsReturned) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert "Multiple cases" in str(excinfo.value)

    def test_bulk_update_without_create_flag_and_no_external_id_raises_error(
        self,
    ):
        data = [
            {
                "case_id": "some-case-id",
                "case_name": "Test Case",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert "A 'create' flag is required" in str(excinfo.value)

    def test_bulk_update_with_create_flag_true(self):
        data = [
            {
                "create": True,
                "case_type": "patient",
                "case_name": "Jane Doe",
                "owner_id": "test-owner",
            }
        ]

        updates = _get_bulk_updates(self.domain, data, self.web_user)

        assert len(updates) == 1
        assert updates[0]._is_case_creation

    def test_bulk_update_with_create_flag_false(self):
        data = [
            {
                "create": False,
                "case_id": "existing-case",
                "case_name": "Updated Name",
            }
        ]

        updates = _get_bulk_updates(self.domain, data, self.web_user)

        assert len(updates) == 1
        assert not updates[0]._is_case_creation
        assert updates[0].case_id == "existing-case"

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_with_case_id_and_external_id_no_lookup(
        self, mock_get_by_external_id
    ):
        data = [
            {
                "case_id": "case-123",
                "case_name": "Test Case",
                "external_id": "ext-456",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        # Should require create flag since case_id is present
        assert "A 'create' flag is required" in str(excinfo.value)
        # External ID lookup should NOT be called
        mock_get_by_external_id.assert_not_called()

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_multiple_rows_mixed_scenarios(
        self, mock_get_by_external_id
    ):

        def get_case_by_external_id(domain, external_id, raise_multiple=False):
            if external_id == "ext-existing":
                existing_case = MagicMock(spec=CommCareCase)
                existing_case.case_id = "existing-case-id"
                return existing_case
            elif external_id == "ext-new":
                return None
            return None

        mock_get_by_external_id.side_effect = get_case_by_external_id

        data = [
            {
                "create": True,
                "case_type": "patient",
                "case_name": "Case with create flag",
                "owner_id": "test-owner",
            },
            {
                "case_name": "Case with existing external_id",
                "external_id": "ext-existing",
            },
            {
                "case_type": "patient",
                "case_name": "Case with new external_id",
                "external_id": "ext-new",
                "owner_id": "test-owner",
            },
        ]

        updates = _get_bulk_updates(self.domain, data, self.web_user)

        assert len(updates) == 3
        # First update: explicit create
        assert updates[0]._is_case_creation
        # Second update: upsert on existing case
        assert not updates[1]._is_case_creation
        assert updates[1].case_id == "existing-case-id"
        # Third update: upsert creates new case
        assert updates[2]._is_case_creation

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_error_in_one_row_reports_all_errors(
        self, mock_get_by_external_id
    ):
        mock_get_by_external_id.return_value = None

        data = [
            {
                # Missing required fields for creation
                "external_id": "ext-123",
            },
            {
                # No create flag, no external_id
                "case_id": "case-456",
                "case_name": "Test",
            },
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        error_message = str(excinfo.value)
        # Should have errors for both rows
        assert "Error in row 1" in error_message
        assert "Error in row 2" in error_message

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_bulk_update_preserves_data_in_original_dict(
        self, mock_get_by_external_id
    ):
        existing_case = MagicMock(spec=CommCareCase)
        existing_case.case_id = "existing-case-id"
        mock_get_by_external_id.return_value = existing_case

        data = [
            {
                "case_name": "Test Case",
                "external_id": "ext-123",
            }
        ]

        _get_bulk_updates(self.domain, data, self.web_user)

        # Data should have been modified (case_id added)
        assert "case_id" in data[0]
        assert data[0]["case_id"] == "existing-case-id"
        # But external_id should still be there
        assert data[0]["external_id"] == "ext-123"
