import uuid

from django.test import TestCase

import pytest

from casexml.apps.case.mock import CaseBlock

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded

from ..api.core import UserError
from ..api.updates import (
    JsonCaseUpsert,
    _get_bulk_updates,
    _get_individual_update,
    handle_case_update,
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
            data,
            self.web_user.user_id,
            is_creation=True
        )

        assert update.is_new_case

    def test_individual_update_with_is_creation_false(self):
        data = {
            "case_id": "existing-case",
            "case_name": "Updated Name",
        }

        update = _get_individual_update(
            data,
            self.web_user.user_id,
            is_creation=False
        )

        assert not update.is_new_case
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
            _get_bulk_updates(data, self.web_user.user_id)

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

        updates = _get_bulk_updates(data, self.web_user.user_id)

        assert len(updates) == 1
        assert updates[0].is_new_case

    def test_bulk_update_with_create_false(self):
        data = [
            {
                "create": False,
                "case_id": "existing-case",
                "case_name": "Updated Name",
            }
        ]

        updates = _get_bulk_updates(data, self.web_user.user_id)

        assert len(updates) == 1
        assert not updates[0].is_new_case
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

        updates = _get_bulk_updates(data, self.web_user.user_id)

        assert len(updates) == 1
        assert isinstance(updates[0], JsonCaseUpsert)
        with pytest.raises(ValueError):
            # is_new_case raises ValueError until get_case_id() initializes its value
            updates[0].is_new_case
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
            _get_bulk_updates(data, self.web_user.user_id)

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
            _get_bulk_updates(data, self.web_user.user_id)

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
            _get_bulk_updates(data, self.web_user.user_id)

        error_message = str(excinfo.value)
        assert "Error in row 1" in error_message
        assert "owner_id" in error_message


@sharded
class TestUpsertIntegration(TestCase):
    """End-to-end tests for UPSERT through handle_case_update()."""
    domain = "test-upsert-integration"

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

    def test_upsert_creates_case_when_external_id_not_found(self):
        data = [
            {
                "create": None,
                "case_type": "patient",
                "case_name": "New Patient",
                "external_id": "new-ext-id",
                "owner_id": self.web_user.user_id,
            }
        ]

        xform, cases = handle_case_update(
            self.domain,
            data,
            self.web_user,
            device_id="test",
            is_creation=None,
        )

        assert len(cases) == 1
        case = cases[0]
        assert case.name == "New Patient"
        assert case.external_id == "new-ext-id"
        assert case.type == "patient"

    def test_upsert_with_missing_external_id(self):
        data = [
            {
                "create": None,
                "case_type": "patient",
                "case_name": "New Patient",
                "owner_id": self.web_user.user_id,
            }
        ]

        with pytest.raises(UserError):
            handle_case_update(
                self.domain,
                data,
                self.web_user,
                device_id="test",
                is_creation=None,
            )

    def test_upsert_create_with_missing_data(self):
        data = [
            {
                "create": None,
                "external_id": "new-ext-id",
                "owner_id": self.web_user.user_id,
            }
        ]

        with pytest.raises(
            ValueError,
            match='required for new case new-ext-id',
        ):
            handle_case_update(
                self.domain,
                data,
                self.web_user,
                device_id="test",
                is_creation=None,
            )

    def test_upsert_updates_case_when_external_id_exists(self):
        existing_case_id = str(uuid.uuid4())
        case_block = CaseBlock(
            case_id=existing_case_id,
            case_type="patient",
            case_name="Original Name",
            external_id="existing-ext-id",
            owner_id=self.web_user.user_id,
            create=True,
        )
        submit_case_blocks(case_block.as_text(), domain=self.domain)

        data = [
            {
                "create": None,
                # case_type not required for update
                "case_name": "Updated Name",
                "external_id": "existing-ext-id",
                "owner_id": self.web_user.user_id,
                "properties": {"status": "updated"},
            }
        ]

        xform, cases = handle_case_update(
            self.domain,
            data,
            self.web_user,
            device_id="test",
            is_creation=None,
        )

        assert len(cases) == 1
        case = cases[0]
        assert case.case_id == existing_case_id
        assert case.name == "Updated Name"
        assert case.get_case_property("status") == "updated"

    def test_bulk_upsert_mixed_creates_and_updates(self):
        existing_case_id = str(uuid.uuid4())
        case_block = CaseBlock(
            case_id=existing_case_id,
            case_type="patient",
            case_name="Existing Patient",
            external_id="ext-existing",
            owner_id=self.web_user.user_id,
            create=True,
        )
        submit_case_blocks(case_block.as_text(), domain=self.domain)

        data = [
            {
                "create": None,
                "case_type": "patient",
                "case_name": "Updated Existing",
                "external_id": "ext-existing",
                "owner_id": self.web_user.user_id,
            },
            {
                "create": None,
                "case_type": "patient",
                "case_name": "Brand New",
                "external_id": "ext-new",
                "owner_id": self.web_user.user_id,
            },
        ]

        xform, cases = handle_case_update(
            self.domain,
            data,
            self.web_user,
            device_id="test",
            is_creation=None,
        )

        assert len(cases) == 2

        updated_case = next(c for c in cases if c.external_id == "ext-existing")
        new_case = next(c for c in cases if c.external_id == "ext-new")

        assert updated_case.case_id == existing_case_id
        assert updated_case.name == "Updated Existing"

        assert new_case.case_id != existing_case_id
        assert new_case.name == "Brand New"
