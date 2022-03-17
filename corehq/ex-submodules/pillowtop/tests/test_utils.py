from datetime import datetime
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from corehq.apps.es.client import BulkActionItem
from corehq.apps.es.tests.utils import es_test
from corehq.form_processor.document_stores import CaseDocumentStore
from corehq.form_processor.models import CommCareCase
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.feed.interface import Change
from pillowtop.utils import build_bulk_payload, ensure_document_exists


class TestEnsureDocumentExists(TestCase):
    domain = 'ensure-domain'

    def _create_change(self):
        now = datetime.utcnow()
        case = CommCareCase(
            case_id=uuid4().hex,
            domain=self.domain,
            modified_on=now,
            server_modified_on=now,
        )
        case.save()

        change = Change(case.case_id, 'seq', document_store=CaseDocumentStore(self.domain))
        return change, case

    def test_handle_existing_doc(self):
        '''
        Should not raise an error when the doc exists
        '''
        change, case = self._create_change()
        ensure_document_exists(change)

    def test_handle_deleted_doc(self):
        '''
        Should not raise an error when the doc has been deleted
        '''
        change, case = self._create_change()
        CommCareCase.objects.soft_delete_cases(self.domain, [case.case_id])
        ensure_document_exists(change)

    def test_handle_missing_doc(self):
        '''
        Should indicate error when the doc is not found

        Note: behavior is different for different document store
        implementations. `CaseDocumentStore` has the behavior tested
        here, while `CouchDocumentStore` raises `DocumentNotFoundError`
        for missing documents.
        '''
        change, case = self._create_change()
        change.id = 'missing'
        ensure_document_exists(change)
        self.assertIsNone(change.document)
        self.assertIsInstance(change.error_raised, DocumentNotFoundError)


@es_test
class TestBuildBulkPayload(SimpleTestCase):

    def test_build_bulk_payload_performs_delete_for__is_deleted_change(self):
        change = DummyChange("1", None, True)
        expected = [BulkActionItem.delete_id(change.id)]
        self.assertEqual(expected, build_bulk_payload([change]))

    def test_build_bulk_payload_performs_index_for_not__is_deleted_change(self):
        change = DummyChange("1", "foo", False)
        expected = [BulkActionItem.index(change.get_document())]
        self.assertEqual(expected, build_bulk_payload([change]))

    def test_build_bulk_payload_discards_delete_change_for_not__is_deleted(self):
        change = DummyChange("1", "foo", True)
        self.assertEqual([], build_bulk_payload([change]))


class DummyChange:

    def __init__(self, id, doc_type, deleted):
        self.id = id
        self.doc_type = doc_type
        self.deleted = deleted

    def get_document(self):
        return {
            "_id": self.id,
            "doc_type": self.doc_type,
        }
