import os
import uuid
from couchdbkit import ResourceNotFound, RequestFailed
from django.test import TestCase
from mock import MagicMock
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper import submit_form_locally
from couchforms.models import XFormDeprecated, XFormInstance, \
    UnfinishedSubmissionStub
from couchforms.tests.testutils import post_xform_to_couch
from dimagi.utils.parsing import json_format_datetime


class EditFormTest(TestCase):
    ID = '7H46J37FGH3'
    domain = 'test-form-edits'

    def tearDown(self):
        try:
            XFormInstance.get_db().delete_doc(self.ID)
        except ResourceNotFound:
            pass
        deprecated_xforms = XFormDeprecated.view(
            'couchforms/edits',
            include_docs=True,
        ).all()
        for form in deprecated_xforms:
            form.delete()

    def _get_files(self):
        first_file = os.path.join(os.path.dirname(__file__), "data", "deprecation", "original.xml")
        edit_file = os.path.join(os.path.dirname(__file__), "data", "deprecation", "edit.xml")

        with open(first_file, "rb") as f:
            xml_data1 = f.read()
        with open(edit_file, "rb") as f:
            xml_data2 = f.read()

        return xml_data1, xml_data2

    def test_basic_edit(self):
        xml_data1, xml_data2 = self._get_files()

        docs = []

        doc = post_xform_to_couch(xml_data1)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])
        doc.domain = self.domain
        doc.save()

        doc = post_xform_to_couch(xml_data2, domain=self.domain)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("100", doc.form['vitals']['height'])
        self.assertEqual("Edited Baby!", doc.form['assessment']['categories'])

        docs.append(doc)

        doc = XFormDeprecated.view('couchforms/edits', include_docs=True).first()
        self.assertEqual(self.ID, doc.orig_id)
        self.assertNotEqual(self.ID, doc.get_id)
        self.assertEqual(XFormDeprecated.__name__, doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])

        self.assertEqual(XFormInstance.get_db().fetch_attachment(doc.get_id, 'form.xml'), xml_data1)
        self.assertEqual(XFormInstance.get_db().fetch_attachment(self.ID, 'form.xml'), xml_data2)

        for doc in docs:
            doc.delete()

    def test_broken_save(self):
        """
        Test that if the second form submission terminates unexpectedly
        and the main form isn't saved, then there are no side effects
        such as the original having been marked as deprecated.
        """

        class BorkDB(object):
            """context manager for making a db's bulk_save temporarily fail"""
            def __init__(self, db):
                self.old = {}
                self.db = db

            def __enter__(self):
                self.old['bulk_save'] = self.db.bulk_save
                self.db.bulk_save = MagicMock(name='bulk_save',
                                              side_effect=RequestFailed())

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.db.bulk_save = self.old['bulk_save']

        self.assertEqual(
            XFormInstance.view('couchforms/edits', key=self.ID).count(), 0)
        self.assertFalse(XFormInstance.get_db().doc_exist(self.ID))

        xml_data1, xml_data2 = self._get_files()

        submit_form_locally(xml_data1, self.domain)
        doc = XFormInstance.get(self.ID)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual(self.domain, doc.domain)

        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            0
        )

        with BorkDB(XFormInstance.get_db()):
            with self.assertRaises(RequestFailed):
                submit_form_locally(xml_data2, self.domain)

        # it didn't go through, so make sure there are no edits still
        self.assertEqual(
            XFormInstance.view('couchforms/edits', key=self.ID).count(), 0)
        self.assertTrue(XFormInstance.get_db().doc_exist(self.ID))
        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID,
                                                    saved=False).count(),
            1
        )
        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            1
        )

    def test_case_management(self):
        form_id = uuid.uuid4().hex
        case_id = uuid.uuid4().hex
        owner_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            owner_id=owner_id,
            version=V2,
            update={
                'property': 'original value'
            }
        ).as_string(format_datetime=json_format_datetime)
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # validate some assumptions
        case = CommCareCase.get(case_id)
        self.assertEqual(case.type, 'person')
        self.assertEqual(case.property, 'original value')
        self.assertEqual([form_id], case.xform_ids)
        self.assertEqual(2, len(case.actions))
        for a in case.actions:
            self.assertEqual(form_id, a.xform_id)

        # submit a new form with a different case update
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='newtype',
            owner_id=owner_id,
            version=V2,
            update={
                'property': 'edited value'
            }
        ).as_string(format_datetime=json_format_datetime)
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        case = CommCareCase.get(case_id)
        self.assertEqual(case.type, 'newtype')
        self.assertEqual(case.property, 'edited value')
        self.assertEqual([form_id], case.xform_ids)
        self.assertEqual(2, len(case.actions))
        for a in case.actions:
            self.assertEqual(form_id, a.xform_id)
