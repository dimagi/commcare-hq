from unittest.mock import MagicMock, patch

from django.test import TestCase

import pytest

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded

from ..api.core import UserError
from ..api.updates import _get_bulk_updates, _get_individual_update


@sharded
class TestIndividualUpdateUpsert(TestCase):
    """
    Test the upsert functionality on external_id in
    ``_get_individual_update()``
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
    def test_upsert_with_external_id_no_existing_case_creates(
        self, mock_get_by_external_id
    ):
        mock_get_by_external_id.return_value = None

        data = {
            "create": None,
            "case_type": "patient",
            "case_name": "John Doe",
            "external_id": "ext-123",
            "owner_id": "test-owner",
        }

        update = _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert update._is_case_creation
        assert update.external_id == "ext-123"
        mock_get_by_external_id.assert_called_once_with(
            self.domain, "ext-123", raise_multiple=True
        )

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_upsert_with_external_id_existing_case_updates(
        self, mock_get_by_external_id
    ):
        existing_case = MagicMock(spec=CommCareCase)
        existing_case.case_id = "existing-case-id"
        mock_get_by_external_id.return_value = existing_case

        data = {
            "create": None,
            "case_name": "John Doe Updated",
            "external_id": "ext-123",
        }

        update = _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert not update._is_case_creation
        assert update.case_id == "existing-case-id"
        assert update.external_id == "ext-123"
        mock_get_by_external_id.assert_called_once_with(
            self.domain, "ext-123", raise_multiple=True
        )

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_upsert_with_external_id_multiple_cases_raises_error(
        self, mock_get_by_external_id
    ):
        mock_get_by_external_id.side_effect = (
            CommCareCase.MultipleObjectsReturned(
                "Multiple cases found with external_id ext-123"
            )
        )

        data = {
            "create": None,
            "case_type": "patient",
            "case_name": "John Doe",
            "external_id": "ext-123",
            "owner_id": "test-owner",
        }

        with pytest.raises(CommCareCase.MultipleObjectsReturned) as excinfo:
            _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert "Multiple cases" in str(excinfo.value)

    def test_upsert_without_external_id_raises_error(self):
        data = {
            "create": None,
            "case_id": "some-case-id",
            "case_name": "Test Case",
        }

        with pytest.raises(UserError) as excinfo:
            _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert "UPSERT operation requires a value for" in str(excinfo.value)

    def test_individual_update_with_is_creation_true(self):
        data = {
            "case_type": "patient",
            "case_name": "Jane Doe",
            "owner_id": "test-owner",
        }

        update = _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert update._is_case_creation

    def test_individual_update_with_is_creation_false(self):
        data = {
            "case_id": "existing-case",
            "case_name": "Updated Name",
        }

        update = _get_individual_update(self.domain, data, self.web_user, is_creation=False)

        assert not update._is_case_creation
        assert update.case_id == "existing-case"

    @patch(
        "corehq.apps.hqcase.api.updates.CommCareCase.objects.get_case_by_external_id"
    )
    def test_upsert_with_case_id_and_external_id_no_lookup(
        self, mock_get_by_external_id
    ):
        data = {
            "create": None,
            "case_id": "case-123",
            "case_name": "Test Case",
            "external_id": "ext-456",
        }

        with pytest.raises(UserError) as excinfo:
            _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert "UPSERT operation requires a value for" in str(excinfo.value)
        mock_get_by_external_id.assert_not_called()

    def test_individual_update_with_create_flag_overrides_is_creation(self):
        data = {
            "create": False,
            "case_id": "existing-case",
            "case_name": "Test Case",
        }

        update = _get_individual_update(self.domain, data, self.web_user, is_creation=True)

        assert not update._is_case_creation
        assert update.case_id == "existing-case"
        assert 'create' not in data


@sharded
class TestBulkUpdates(TestCase):
    """
    Test that ``_get_bulk_updates()`` requires a 'create' flag in each
    data item and delegates to ``_get_individual_update()``.
    """

    domain = "test-bulk-updates"

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

    def test_bulk_update_missing_create_flag_raises_error(self):
        data = [
            {
                "case_id": "some-case-id",
                "case_name": "Test Case",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert "A 'create' flag is required" in str(excinfo.value)

    def test_bulk_update_with_create_true(self):
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

    def test_bulk_update_with_create_false(self):
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
    def test_bulk_update_with_create_none_upserts(self, mock_get_by_external_id):
        existing_case = MagicMock(spec=CommCareCase)
        existing_case.case_id = "existing-case-id"
        mock_get_by_external_id.return_value = existing_case

        data = [
            {
                "create": None,
                "case_name": "Test Case",
                "external_id": "ext-123",
            }
        ]

        updates = _get_bulk_updates(self.domain, data, self.web_user)

        assert len(updates) == 1
        assert not updates[0]._is_case_creation
        assert updates[0].case_id == "existing-case-id"
        mock_get_by_external_id.assert_called_once()

    def test_bulk_update_with_error_reports_row_number(self):
        data = [
            {
                "create": True,
                # Missing required fields for creation (no owner_id)
                "case_type": "patient",
                "case_name": "Missing owner_id",
            },
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        error_message = str(excinfo.value)
        assert "Error in row 1" in error_message
        assert "owner_id" in error_message
