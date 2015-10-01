from datetime import datetime, timedelta
import os
import uuid
from django.test import TestCase
from mock import MagicMock
from couchdbkit import RequestFailed
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.xml import V2
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper import submit_form_locally
from couchforms.models import XFormDeprecated, XFormInstance, \
    UnfinishedSubmissionStub

from corehq.form_processor.interfaces import FormProcessorInterface


class EditFormTest(TestCase):
    ID = '7H46J37FGH3'
    domain = 'test-form-edits'

    def tearDown(self):
        XFormInstance.get_db().flush()

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
        yesterday = datetime.utcnow() - timedelta(days=1)

        xform = FormProcessorInterface.post_xform(xml_data1)
        self.assertEqual(self.ID, xform.id)
        self.assertEqual("XFormInstance", xform.doc_type)
        self.assertEqual("", xform.form['vitals']['height'])
        self.assertEqual("other", xform.form['assessment']['categories'])

        # post form back in time to simulate an edit
        FormProcessorInterface.update_properties(
            xform,
            domain=self.domain,
            received_on=yesterday,
        )

        xform = FormProcessorInterface.post_xform(xml_data2, domain=self.domain)
        self.assertEqual(self.ID, xform.id)
        self.assertEqual("XFormInstance", xform.doc_type)
        self.assertEqual("100", xform.form['vitals']['height'])
        self.assertEqual("Edited Baby!", xform.form['assessment']['categories'])

        [deprecated_xform] = FormProcessorInterface.get_by_doc_type(self.domain, 'XFormDeprecated')

        self.assertEqual(self.ID, deprecated_xform.orig_id)
        self.assertNotEqual(self.ID, deprecated_xform.id)
        self.assertEqual('XFormDeprecated', deprecated_xform.doc_type)
        self.assertEqual("", deprecated_xform.form['vitals']['height'])
        self.assertEqual("other", deprecated_xform.form['assessment']['categories'])

        self.assertEqual(xform.received_on, deprecated_xform.received_on)
        self.assertEqual(xform.deprecated_form_id, deprecated_xform.id)
        self.assertTrue(xform.edited_on > deprecated_xform.received_on)

        self.assertEqual(
            FormProcessorInterface.get_attachment(deprecated_xform.id, 'form.xml'),
            xml_data1
        )
        self.assertEqual(FormProcessorInterface.get_attachment(self.ID, 'form.xml'), xml_data2)

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

        xforms = FormProcessorInterface.get_by_doc_type(self.domain, 'XFormInstance')
        self.assertEqual(len(xforms), 0)

        xml_data1, xml_data2 = self._get_files()

        submit_form_locally(xml_data1, self.domain)
        xform = FormProcessorInterface.get_xform(self.ID)
        self.assertEqual(self.ID, xform.id)
        self.assertEqual("XFormInstance", xform.doc_type)
        self.assertEqual(self.domain, xform.domain)

        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            0
        )

        # This seems like a couch specific test util. Will likely need postgres test utils
        with BorkDB(XFormInstance.get_db()):
            with self.assertRaises(RequestFailed):
                submit_form_locally(xml_data2, self.domain)

        # it didn't go through, so make sure there are no edits still
        xforms = FormProcessorInterface.get_by_doc_type(self.domain, 'XFormDeprecated')
        self.assertEqual(len(xforms), 0)
        xform = FormProcessorInterface.get_xform(self.ID)
        self.assertIsNotNone(xform)
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
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # validate some assumptions
        case = FormProcessorInterface.get_case(case_id)
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
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        case = FormProcessorInterface.get_case(case_id)
        self.assertEqual(case.type, 'newtype')
        self.assertEqual(case.property, 'edited value')
        self.assertEqual([form_id], case.xform_ids)
        self.assertEqual(2, len(case.actions))
        for a in case.actions:
            self.assertEqual(form_id, a.xform_id)

    def test_second_edit_fails(self):
        form_id = uuid.uuid4().hex
        case_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            version=V2,
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # submit an edit form with a bad case update (for example a bad ID)
        case_block = CaseBlock(
            create=True,
            case_id='',
            case_type='person',
            version=V2,
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        xform = FormProcessorInterface.get_xform(form_id)
        self.assertEqual('XFormError', xform.doc_type)

        deprecated_xform = FormProcessorInterface.get_xform(xform.deprecated_form_id)
        self.assertEqual('XFormDeprecated', deprecated_xform.doc_type)

    def test_case_management_ordering(self):
        case_id = uuid.uuid4().hex
        owner_id = uuid.uuid4().hex

        # create a case
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            owner_id=owner_id,
            version=V2,
        ).as_string()
        create_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = FormProcessorInterface.get_case(case_id)
        self.assertEqual([create_form_id], case.xform_ids)
        self.assertEqual([create_form_id], [a.xform_id for a in case.actions])
        for a in case.actions:
            self.assertEqual(create_form_id, a.xform_id)

        edit_date = datetime.utcnow()
        # set some property value
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            version=V2,
            date_modified=edit_date,
            update={
                'property': 'first value',
            }
        ).as_string()
        edit_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = FormProcessorInterface.get_case(case_id)
        self.assertEqual(case.property, 'first value')
        self.assertEqual([create_form_id, edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id], [a.xform_id for a in case.actions])

        # submit a second (new) form updating the value
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            version=V2,
            update={
                'property': 'final value',
            }
        ).as_string()
        second_edit_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = FormProcessorInterface.get_case(case_id)
        self.assertEqual(case.property, 'final value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], [a.xform_id for a in
            case.actions])

        # deprecate the middle edit
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            version=V2,
            date_modified=edit_date,  # need to use the previous edit date for action sort comparisons
            update={
                'property': 'edited value',
                'added_property': 'added value',
            }
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=edit_form_id)

        # ensure that the middle edit stays in the right place and is applied
        # before the final one
        case = FormProcessorInterface.get_case(case_id)
        self.assertEqual(case.property, 'final value')
        self.assertEqual(case.added_property, 'added value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], [a.xform_id for a in
            case.actions])
