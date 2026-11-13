import uuid

from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.mock import CaseBlock
from django.test import TestCase

from corehq.apps.cleanup.deleted_forms import (
    iter_scan_pages,
    repair_case,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import (
    CaseTransaction,
    CommCareCase,
    RebuildWithReason,
    XFormInstance,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded

DOMAIN = 'deleted-forms'


def submit_form(case_id, create=False, update=None, domain=DOMAIN):
    block = CaseBlock(case_id=case_id, create=create, update=update or {})
    xform, _ = submit_case_blocks([block.as_text()], domain)
    return xform.form_id


def create_case_with_update(domain=DOMAIN):
    """Return ``(case_id, create_form_id, update_form_id)``"""
    case_id = uuid.uuid4().hex
    create_form_id = submit_form(
        case_id, create=True, update={'prop': 'created'}, domain=domain
    )
    update_form_id = submit_form(
        case_id, update={'prop': 'updated'}, domain=domain
    )
    return case_id, create_form_id, update_form_id


def hard_delete(form_id, domain=DOMAIN):
    XFormInstance.objects.hard_delete_forms(domain, [form_id])


def delete_all_cases_and_forms():
    # plproxy writes are not rolled back with the test transaction
    for domain in (DOMAIN, 'other-domain'):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(domain)


def scan(domain=DOMAIN, **kwargs):
    deleted = {}
    for page in iter_scan_pages(domain, **kwargs):
        deleted.update(page.deleted_form_ids_by_case)
    return deleted


@sharded
class TestIterScanPages(TestCase):
    def setUp(self):
        self.case_id, self.create_form_id, self.update_form_id = (
            create_case_with_update()
        )

    def tearDown(self):
        delete_all_cases_and_forms()
        super().tearDown()

    def test_healthy_case_is_not_reported(self):
        assert scan() == {}

    def test_soft_deleted_form_is_reported(self):
        XFormInstance.objects.soft_delete_forms(DOMAIN, [self.update_form_id])
        assert scan() == {self.case_id: {self.update_form_id}}

    def test_hard_deleted_form_is_reported(self):
        hard_delete(self.update_form_id)
        assert scan() == {self.case_id: {self.update_form_id}}

    def test_archived_then_hard_deleted_form_is_not_reported(self):
        XFormInstance.objects.get_form(self.update_form_id).archive()
        hard_delete(self.update_form_id)
        assert scan() == {}

    def test_resume_from_each_position_finds_remaining_cases(self):
        broken = {self.case_id: {self.update_form_id}}
        hard_delete(self.update_form_id)
        for _ in range(4):
            case_id, _, form_id = create_case_with_update()
            hard_delete(form_id)
            broken[case_id] = {form_id}

        pages = list(iter_scan_pages(DOMAIN, page_size=2))
        for i, page in enumerate(pages):
            seen = {}
            for earlier in pages[: i + 1]:
                seen.update(earlier.deleted_form_ids_by_case)
            rest = scan(position=page.position, page_size=2)
            assert seen.keys().isdisjoint(rest.keys())
            assert {**seen, **rest} == broken


@sharded
class TestRepairCase(TestCase):
    def setUp(self):
        self.case_id, self.create_form_id, self.update_form_id = (
            create_case_with_update()
        )

    def tearDown(self):
        delete_all_cases_and_forms()
        super().tearDown()

    def test_repaired_case_can_be_rebuilt(self):
        hard_delete(self.update_form_id)
        with self.assertRaises(XFormNotFound):
            self.rebuild()

        assert repair_case(DOMAIN, self.case_id, [self.update_form_id]) == 1

        self.rebuild()  # does not raise
        assert scan() == {}

    def test_deleted_form_updates_are_removed_from_case(self):
        hard_delete(self.update_form_id)
        repair_case(DOMAIN, self.case_id, [self.update_form_id])
        assert self.case().get_case_property('prop') == 'created'

    def test_only_deleted_form_transactions_are_revoked(self):
        hard_delete(self.update_form_id)
        repair_case(DOMAIN, self.case_id, [self.update_form_id])
        assert self.transaction(self.update_form_id).revoked
        assert not self.transaction(self.create_form_id).revoked

    def test_undeleted_form_is_not_revoked(self):
        assert repair_case(DOMAIN, self.case_id, [self.update_form_id]) == 0
        assert not self.transaction(self.update_form_id).revoked
        assert self.case().get_case_property('prop') == 'updated'

    def test_soft_deleted_form_is_revoked(self):
        XFormInstance.objects.soft_delete_forms(DOMAIN, [self.update_form_id])
        assert repair_case(DOMAIN, self.case_id, [self.update_form_id]) == 1
        assert self.transaction(self.update_form_id).revoked
        assert self.case().get_case_property('prop') == 'created'

    def test_already_repaired_case_is_not_rebuilt_again(self):
        hard_delete(self.update_form_id)
        repair_case(DOMAIN, self.case_id, [self.update_form_id])
        modified_on = self.case().server_modified_on
        assert repair_case(DOMAIN, self.case_id, [self.update_form_id]) == 0
        assert self.case().server_modified_on == modified_on

    def test_case_in_other_domain_is_not_revoked(self):
        hard_delete(self.update_form_id)
        assert (
            repair_case('other-domain', self.case_id, [self.update_form_id])
            == 0
        )
        assert not self.transaction(self.update_form_id).revoked

    def case(self):
        return CommCareCase.objects.get_case(self.case_id, DOMAIN)

    def transaction(self, form_id):
        return CaseTransaction.objects.get_transaction_by_form_id(
            self.case_id, form_id
        )

    def rebuild(self):
        rebuild_case_from_forms(
            DOMAIN, self.case_id, RebuildWithReason(reason='test')
        )
