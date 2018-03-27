from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.feed.interface import Change
from pillowtop.utils import ensure_document_exists
from casexml.apps.case.models import CommCareCase


class TestEnsureDocumentExists(TestCase):
    domain = 'ensure-domain'

    def _create_change(self):
        case = CommCareCase(domain=self.domain)
        case.save()

        change = Change(
            case._id,
            'seq',
            document_store=CouchDocumentStore(
                CommCareCase.get_db(),
                self.domain,
            )
        )
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
        case.delete()
        ensure_document_exists(change)

    def test_handle_missing_doc(self):
        '''
        Should raise an error when the doc is completely missing
        '''
        change, case = self._create_change()
        change.id = 'missing'
        with self.assertRaises(DocumentNotFoundError):
            ensure_document_exists(change)
