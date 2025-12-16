from django.test import TestCase

import pytest

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded

from ..api.core import UserError
from ..api.updates import (
    JsonCaseUpsert,
    _get_bulk_updates,
    _get_individual_update,
)


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

    def test_bulk_update_with_create_none_returns_upsert(self):
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
        assert isinstance(updates[0], JsonCaseUpsert)
        # _is_case_creation is None until get_case_id() is called
        assert updates[0]._is_case_creation is None
        assert updates[0].external_id == "ext-123"

    def test_bulk_update_with_create_none_without_external_id_raises_error(self):
        data = [
            {
                "create": None,
                "case_name": "Test Case",
                "case_type": "patient",
                "owner_id": "test-owner",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert "UPSERT requires external_id" in str(excinfo.value)

    def test_bulk_update_with_create_none_with_case_id_raises_error(self):
        data = [
            {
                "create": None,
                "case_id": "case-123",
                "case_type": "patient",
                "case_name": "Test Case",
                "external_id": "ext-456",
                "owner_id": "test-owner",
            }
        ]

        with pytest.raises(UserError) as excinfo:
            _get_bulk_updates(self.domain, data, self.web_user)

        assert "UPSERT does not allow case_id" in str(excinfo.value)

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
