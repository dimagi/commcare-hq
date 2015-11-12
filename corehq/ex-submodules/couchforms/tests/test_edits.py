from datetime import datetime, timedelta
import os
import uuid
from django.test import TestCase
from mock import patch
from couchdbkit import RequestFailed
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import TEST_DOMAIN_NAME
from corehq.apps.hqcase.utils import submit_case_blocks
from couchforms.models import (
    UnfinishedSubmissionStub,
)

from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.test_utils import FormProcessorTestUtils, run_with_all_backends
from corehq.util.test_utils import TestFileMixin


class EditFormTest(TestCase, TestFileMixin):
    ID = '7H46J37FGH3'
    domain = 'test-form-edits'

    file_path = ('data', 'deprecation')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.interface = FormProcessorInterface(TEST_DOMAIN_NAME)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        UnfinishedSubmissionStub.objects.all().delete()

    @run_with_all_backends
    def test_basic_edit(self):
        original_xml = self.get_xml('original')
        edit_xml = self.get_xml('edit')
        yesterday = datetime.utcnow() - timedelta(days=1)

        def process(form):
            form.domain = self.domain
            form.received_on = yesterday

        xform = self.interface.post_xform(original_xml, process=process)
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("", xform.form_data['vitals']['height'])
        self.assertEqual("other", xform.form_data['assessment']['categories'])

        xform = self.interface.post_xform(edit_xml, domain=self.domain)
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("100", xform.form_data['vitals']['height'])
        self.assertEqual("Edited Baby!", xform.form_data['assessment']['categories'])

        deprecated_xform = self.interface.xform_model.get(xform.deprecated_form_id)

        self.assertEqual(self.ID, deprecated_xform.orig_id)
        self.assertNotEqual(self.ID, deprecated_xform.form_id)
        self.assertTrue(deprecated_xform.is_deprecated)
        self.assertEqual("", deprecated_xform.form_data['vitals']['height'])
        self.assertEqual("other", deprecated_xform.form_data['assessment']['categories'])

        self.assertEqual(xform.received_on, deprecated_xform.received_on)
        self.assertEqual(xform.deprecated_form_id, deprecated_xform.form_id)
        self.assertTrue(xform.edited_on > deprecated_xform.received_on)

        self.assertEqual(
            deprecated_xform.get_xml(),
            original_xml
        )
        self.assertEqual(xform.get_xml(), edit_xml)

    @run_with_all_backends
    def test_broken_save(self):
        """
        Test that if the second form submission terminates unexpectedly
        and the main form isn't saved, then there are no side effects
        such as the original having been marked as deprecated.
        """

        original_xml = self.get_xml('original')
        edit_xml = self.get_xml('edit')

        _, xform, _ = self.interface.submit_form_locally(original_xml, self.domain)
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual(self.domain, xform.domain)

        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            0
        )

        with patch.object(self.interface.processor, 'bulk_save', side_effect=RequestFailed):
            with self.assertRaises(RequestFailed):
                self.interface.submit_form_locally(edit_xml, self.domain)

        # it didn't go through, so make sure there are no edits still
        self.assertIsNone(getattr(xform, 'deprecated_form_id', None))

        xform = self.interface.xform_model.get(self.ID)
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
            update={
                'property': 'original value'
            }
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # validate some assumptions
        case = self.interface.case_model.get(case_id)
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
            update={
                'property': 'edited value'
            }
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        case = self.interface.case_model.get(case_id)
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
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # submit an edit form with a bad case update (for example a bad ID)
        case_block = CaseBlock(
            create=True,
            case_id='',
            case_type='person',
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        xform = self.interface.xform_model.get(form_id)
        self.assertEqual('XFormError', xform.doc_type)

        deprecated_xform = self.interface.xform_model.get(xform.deprecated_form_id)
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
        ).as_string()
        create_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = self.interface.case_model.get(case_id)
        self.assertEqual([create_form_id], case.xform_ids)
        self.assertEqual([create_form_id], [a.xform_id for a in case.actions])
        for a in case.actions:
            self.assertEqual(create_form_id, a.xform_id)

        edit_date = datetime.utcnow()
        # set some property value
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            date_modified=edit_date,
            update={
                'property': 'first value',
            }
        ).as_string()
        edit_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = self.interface.case_model.get(case_id)
        self.assertEqual(case.property, 'first value')
        self.assertEqual([create_form_id, edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id], [a.xform_id for a in case.actions])

        # submit a second (new) form updating the value
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            update={
                'property': 'final value',
            }
        ).as_string()
        second_edit_form_id = submit_case_blocks(case_block, domain=self.domain)

        # validate that worked
        case = self.interface.case_model.get(case_id)
        self.assertEqual(case.property, 'final value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], [a.xform_id for a in
            case.actions])

        # deprecate the middle edit
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            date_modified=edit_date,  # need to use the previous edit date for action sort comparisons
            update={
                'property': 'edited value',
                'added_property': 'added value',
            }
        ).as_string()
        submit_case_blocks(case_block, domain=self.domain, form_id=edit_form_id)

        # ensure that the middle edit stays in the right place and is applied
        # before the final one
        case = self.interface.case_model.get(case_id)
        self.assertEqual(case.property, 'final value')
        self.assertEqual(case.added_property, 'added value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], [a.xform_id for a in
            case.actions])
