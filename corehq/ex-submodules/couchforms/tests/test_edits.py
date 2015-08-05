from datetime import datetime, timedelta
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


def access_edits(**kwargs):
    return XFormDeprecated.temp_view({'map': """
        function (doc) {
            //function to reveal prior edits of xforms.
            if(doc['doc_type'] == "XFormDeprecated") {
                emit(doc.orig_id, null);
            }
        }
    """}, **kwargs)


class EditFormTest(TestCase):
    ID = '7H46J37FGH3'
    domain = 'test-form-edits'

    def tearDown(self):
        try:
            XFormInstance.get_db().delete_doc(self.ID)
        except ResourceNotFound:
            pass
        deprecated_xforms = access_edits(include_docs=True).all()
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
        yesterday = datetime.utcnow() - timedelta(days=1)
        docs = []

        doc = post_xform_to_couch(xml_data1)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("", doc.form['vitals']['height'])
        self.assertEqual("other", doc.form['assessment']['categories'])
        doc.domain = self.domain
        doc.received_on = yesterday  # set this back in time to simulate an edit
        doc.save()

        doc = post_xform_to_couch(xml_data2, domain=self.domain)
        self.assertEqual(self.ID, doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        self.assertEqual("100", doc.form['vitals']['height'])
        self.assertEqual("Edited Baby!", doc.form['assessment']['categories'])

        docs.append(doc)

        deprecated_doc = access_edits(include_docs=True).first()
        self.assertEqual(self.ID, deprecated_doc.orig_id)
        self.assertNotEqual(self.ID, deprecated_doc._id)
        self.assertEqual(XFormDeprecated.__name__, deprecated_doc.doc_type)
        self.assertEqual("", deprecated_doc.form['vitals']['height'])
        self.assertEqual("other", deprecated_doc.form['assessment']['categories'])

        self.assertEqual(doc.received_on, deprecated_doc.received_on)
        self.assertEqual(doc.deprecated_form_id, deprecated_doc._id)
        self.assertTrue(doc.edited_on > doc.received_on)

        self.assertEqual(XFormInstance.get_db().fetch_attachment(deprecated_doc._id, 'form.xml'), xml_data1)
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

        self.assertEqual(access_edits(key=self.ID).count(), 0)
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
        self.assertEqual(access_edits(key=self.ID).count(), 0)
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

    def test_second_edit_fails(self):
        form_id = uuid.uuid4().hex
        case_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            version=V2,
        ).as_string(format_datetime=json_format_datetime)
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # submit an edit form with a bad case update (for example a bad ID)
        case_block = CaseBlock(
            create=True,
            case_id='',
            case_type='person',
            version=V2,
        ).as_string(format_datetime=json_format_datetime)
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        form = XFormInstance.get(form_id)
        self.assertEqual('XFormError', form.doc_type)

        deprecated_form = XFormInstance.get(form.deprecated_form_id)
        self.assertEqual('XFormDeprecated', deprecated_form.doc_type)

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
        ).as_string(format_datetime=json_format_datetime)
        create_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = CommCareCase.get(case_id)
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
        ).as_string(format_datetime=json_format_datetime)
        edit_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = CommCareCase.get(case_id)
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
        ).as_string(format_datetime=json_format_datetime)
        second_edit_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = CommCareCase.get(case_id)
        self.assertEqual(case.property, 'final value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], [a.xform_id for a in case.actions])

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
        ).as_string(format_datetime=json_format_datetime)
        submit_case_blocks(case_block, domain=self.domain, form_id=edit_form_id)

        # ensure that the middle edit stays in the right place and is applied
        # before the final one
        case = CommCareCase.get(case_id)
        self.assertEqual(case.property, 'final value')
        self.assertEqual(case.added_property, 'added value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], [a.xform_id for a in case.actions])
