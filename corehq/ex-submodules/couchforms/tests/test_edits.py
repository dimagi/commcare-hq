from datetime import datetime, timedelta
import os
import uuid

from django.conf import settings
from django.test import TestCase
from mock import patch
from couchdbkit import RequestFailed
from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.models import (
    UnfinishedSubmissionStub,
)

from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends, post_xform
from corehq.util.test_utils import TestFileMixin


class EditFormTest(TestCase, TestFileMixin):
    ID = '7H46J37FGH3'
    domain = 'test-form-edits'

    file_path = ('data', 'deprecation')
    root = os.path.dirname(__file__)

    def setUp(self):
        self.interface = FormProcessorInterface(self.domain)
        self.casedb = CaseAccessors(self.domain)
        self.formdb = FormAccessors(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        FormProcessorTestUtils.delete_all_cases(self.domain)
        UnfinishedSubmissionStub.objects.all().delete()

    @run_with_all_backends
    def test_basic_edit(self):
        original_xml = self.get_xml('original')
        edit_xml = self.get_xml('edit')

        xform = post_xform(original_xml, domain=self.domain)

        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("", xform.form_data['vitals']['height'])
        self.assertEqual("other", xform.form_data['assessment']['categories'])

        xform = post_xform(edit_xml, domain=self.domain)
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("100", xform.form_data['vitals']['height'])
        self.assertEqual("Edited Baby!", xform.form_data['assessment']['categories'])

        deprecated_xform = self.formdb.get_form(xform.deprecated_form_id)

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

        _, xform, _ = submit_form_locally(original_xml, self.domain)
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual(self.domain, xform.domain)

        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            0
        )

        with patch.object(self.interface.processor, 'save_processed_models', side_effect=RequestFailed):
            with self.assertRaises(RequestFailed):
                submit_form_locally(edit_xml, self.domain)

        # it didn't go through, so make sure there are no edits still
        self.assertIsNone(getattr(xform, 'deprecated_form_id', None))

        xform = self.formdb.get_form(self.ID)
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

    @run_with_all_backends
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
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.type, 'person')
        self.assertEqual(case.dynamic_case_properties()['property'], 'original value')
        self.assertEqual([form_id], case.xform_ids)

        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
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

        case = self.casedb.get_case(case_id)
        self.assertEqual(case.type, 'newtype')
        self.assertEqual(case.dynamic_case_properties()['property'], 'edited value')
        self.assertEqual([form_id], case.xform_ids)

        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self.assertEqual(2, len(case.actions))
            for a in case.actions:
                self.assertEqual(form_id, a.xform_id)

    @run_with_all_backends
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

        xform = self.formdb.get_form(form_id)
        self.assertTrue(xform.is_error)

        deprecated_xform = self.formdb.get_form(xform.deprecated_form_id)
        self.assertTrue(deprecated_xform.is_deprecated)

    @run_with_all_backends
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
        case = self.casedb.get_case(case_id)
        self.assertEqual([create_form_id], case.xform_ids)

        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
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
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties()['property'], 'first value')
        self.assertEqual([create_form_id, edit_form_id], case.xform_ids)

        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
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
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties()['property'], 'final value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)

        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self.assertEqual(
                [create_form_id, edit_form_id, second_edit_form_id],
                [a.xform_id for a in case.actions]
            )

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
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties()['property'], 'final value')
        self.assertEqual(case.dynamic_case_properties()['added_property'], 'added value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)

        if not settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self.assertEqual(
                [create_form_id, edit_form_id, second_edit_form_id],
                [a.xform_id for a in case.actions]
            )
