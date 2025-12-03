from unittest.mock import patch

from django.test import TestCase

import pytest

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded

from ..api.core import UserError
from ..api.updates import _get_bulk_updates, _get_individual_update


@sharded
class TestIndividualUpdate(TestCase):
    domain = "test-individual-update"

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

    def test_individual_update_with_is_creation_true(self):
        data = {
            "case_type": "patient",
            "case_name": "Jane Doe",
            "owner_id": "test-owner",
        }

        update = _get_individual_update(
            self.domain,
            data,
            self.web_user,
            is_creation=True
        )

        assert update._is_case_creation

    def test_individual_update_with_is_creation_false(self):
        data = {
            "case_id": "existing-case",
            "case_name": "Updated Name",
        }

        update = _get_individual_update(
            self.domain,
            data,
            self.web_user,
            is_creation=False
        )

        assert not update._is_case_creation
        assert update.case_id == "existing-case"


@sharded
class TestBulkUpdates(TestCase):
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

    @patch("corehq.apps.hqcase.api.get_bulk.get_bulk")
    def test_bulk_update_with_create_none_upsert_existing_case(self, mock_get_bulk):
        mock_get_bulk.return_value = {
            'cases': [{'case_id': 'existing-case-id', 'external_id': 'ext-123'}],
            'matching_records': 1,
            'missing_records': 0,
        }

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
        mock_get_bulk.assert_called_once_with(
            self.domain, self.web_user, case_ids=[], external_ids=['ext-123']
        )

    @patch("corehq.apps.hqcase.api.get_bulk.get_bulk")
    def test_bulk_update_with_create_none_upsert_no_existing_case(self, mock_get_bulk):
        mock_get_bulk.return_value = {
            'cases': [{'external_id': 'ext-123', 'error': 'not found'}],
            'matching_records': 0,
            'missing_records': 1,
        }

        data = [
            {
                "create": None,
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
        mock_get_bulk.assert_called_once_with(
            self.domain, self.web_user, case_ids=[], external_ids=['ext-123']
        )

    def test_bulk_update_with_create_none_without_external_id_raises_error(self):
        data = [
            {
                "create": None,
                "case_id": "some-case-id",
                "case_name": "Test Case",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert 'UPSERT operation requires "create": null' in str(excinfo.value)
        assert '"external_id" set and "case_id" not set' in str(excinfo.value)

    def test_bulk_update_with_create_none_with_case_id_raises_error(self):
        data = [
            {
                "create": None,
                "case_id": "case-123",
                "case_name": "Test Case",
                "external_id": "ext-456",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert 'UPSERT operation requires "create": null' in str(excinfo.value)
        assert '"external_id" set and "case_id" not set' in str(excinfo.value)

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
