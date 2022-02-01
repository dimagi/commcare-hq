from datetime import datetime
from uuid import uuid4

from django.test import TestCase

from corehq.form_processor.document_stores import CaseDocumentStore
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.feed.interface import Change
from pillowtop.utils import ensure_document_exists


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
        CaseAccessorSQL.soft_delete_cases(self.domain, [case.case_id])
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
