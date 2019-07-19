from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import os
import uuid

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase
from mock import patch
from requests.exceptions import HTTPError
from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.models import UnfinishedSubmissionStub

from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.test_utils import TestFileMixin, softer_assert
from io import open


@softer_assert()
class EditFormTest(TestCase, TestFileMixin):
    ID = '7H46J37FGH3'
    domain = 'test-form-edits'

    file_path = ('data', 'deprecation')
    root = os.path.dirname(__file__)

    def setUp(self):
        super(EditFormTest, self).setUp()
        self.interface = FormProcessorInterface(self.domain)
        self.casedb = CaseAccessors(self.domain)
        self.formdb = FormAccessors(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(self.domain)
        FormProcessorTestUtils.delete_all_cases(self.domain)
        UnfinishedSubmissionStub.objects.all().delete()
        super(EditFormTest, self).tearDown()

    def test_basic_edit(self):
        original_xml = self.get_xml('original')
        edit_xml = self.get_xml('edit')

        xform = submit_form_locally(original_xml, self.domain).xform

        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("", xform.form_data['vitals']['height'])
        self.assertEqual("other", xform.form_data['assessment']['categories'])

        xform = submit_form_locally(edit_xml, self.domain).xform
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("100", xform.form_data['vitals']['height'])
        self.assertEqual("Edited Baby!", xform.form_data['assessment']['categories'])

        self.assertEqual(1, len(xform.history))
        self.assertEqual('edit', xform.history[0].operation)

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
            deprecated_xform.get_xml().decode('utf-8'),
            original_xml.decode('utf-8')
        )
        self.assertEqual(xform.get_xml().decode('utf-8'), edit_xml.decode('utf-8'))

    def test_edit_form_with_attachments(self):
        attachment_source = './corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg'
        attachment_file = open(attachment_source, 'rb')
        attachments = {
            'fruity_file': UploadedFile(attachment_file, 'fruity_file', content_type='image/jpeg')
        }

        def _get_xml(date, form_id):
            return """<?xml version='1.0' ?>
               <data uiVersion="1" version="1" name="" xmlns="http://openrosa.org/formdesigner/123">
                   <name>fgg</name>
                   <date>2011-06-07</date>
                   <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
                       <n1:deviceID>354957031935664</n1:deviceID>
                       <n1:timeStart>{date}</n1:timeStart>
                       <n1:timeEnd>{date}</n1:timeEnd>
                       <n1:username>bcdemo</n1:username>
                       <n1:userID>user-abc</n1:userID>
                       <n1:instanceID>{form_id}</n1:instanceID>
                   </n1:meta>
               </data>""".format(
                date=date,
                attachment_source=attachment_source,
                form_id=form_id
            )
        form_id = uuid.uuid4().hex
        original_xml = _get_xml('2016-03-01T12:04:16Z', form_id)
        submit_form_locally(
            original_xml,
            self.domain,
            attachments=attachments,
        )
        form = self.formdb.get_form(form_id)
        self.assertIn('fruity_file', form.attachments)
        self.assertIn(original_xml, form.get_xml().decode('utf-8'))

        # edit form
        edit_xml = _get_xml('2016-04-01T12:04:16Z', form_id)
        submit_form_locally(
            edit_xml,
            self.domain,
        )
        form = self.formdb.get_form(form_id)
        self.assertIsNotNone(form.edited_on)
        self.assertIsNotNone(form.deprecated_form_id)
        self.assertIn('fruity_file', form.attachments)
        self.assertIn(edit_xml, form.get_xml().decode('utf-8'))

    def test_edit_an_error(self):
        form_id = uuid.uuid4().hex
        case_block = CaseBlock(
            create=True,
            case_id='',  # this should cause the submission to error
            case_type='person',
            owner_id='some-owner',
        )

        form, _ = submit_case_blocks(case_block.as_text(), domain=self.domain, form_id=form_id)
        self.assertTrue(form.is_error)
        self.assertTrue('IllegalCaseId' in form.problem)

        case_block.case_id = uuid.uuid4().hex
        form, _ = submit_case_blocks(case_block.as_text(), domain=self.domain, form_id=form_id)
        self.assertFalse(form.is_error)
        self.assertEqual(None, getattr(form, 'problem', None))

    def test_broken_save(self):
        """
        Test that if the second form submission terminates unexpectedly
        and the main form isn't saved, then there are no side effects
        such as the original having been marked as deprecated.
        """

        original_xml = self.get_xml('original')
        edit_xml = self.get_xml('edit')

        result = submit_form_locally(original_xml, self.domain)
        xform = result.xform
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual(self.domain, xform.domain)

        self.assertEqual(
            UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(),
            0
        )

        with patch.object(self.interface.processor, 'save_processed_models', side_effect=HTTPError):
            with self.assertRaises(HTTPError):
                submit_form_locally(edit_xml, self.domain)

        xform = self.formdb.get_form(self.ID)
        self.assertIsNotNone(xform)
        # it didn't go through, so make sure there are no edits still
        self.assertIsNone(getattr(xform, 'deprecated_form_id', None))
        self.assertEqual(UnfinishedSubmissionStub.objects.filter(xform_id=self.ID).count(), 0)

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
        ).as_string().decode('utf-8')
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # validate some assumptions
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.type, 'person')
        self.assertEqual(case.dynamic_case_properties()['property'], 'original value')
        self.assertEqual([form_id], case.xform_ids)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
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
        ).as_string().decode('utf-8')
        xform, _ = submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        case = self.casedb.get_case(case_id)
        self.assertEqual(case.type, 'newtype')
        self.assertEqual(case.dynamic_case_properties()['property'], 'edited value')
        self.assertEqual([form_id], case.xform_ids)
        self.assertEqual(case.server_modified_on, xform.edited_on)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
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
        ).as_string().decode('utf-8')
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        # submit an edit form with a bad case update (for example a bad ID)
        case_block = CaseBlock(
            create=True,
            case_id='',
            case_type='person',
        ).as_string().decode('utf-8')
        submit_case_blocks(case_block, domain=self.domain, form_id=form_id)

        xform = self.formdb.get_form(form_id)
        self.assertTrue(xform.is_error)

        deprecated_xform = self.formdb.get_form(xform.deprecated_form_id)
        self.assertTrue(deprecated_xform.is_deprecated)

    def test_case_management_ordering(self):
        case_id = uuid.uuid4().hex
        owner_id = uuid.uuid4().hex

        # create a case
        case_block = CaseBlock(
            create=True,
            case_id=case_id,
            case_type='person',
            owner_id=owner_id,
        ).as_string().decode('utf-8')
        create_form_id = submit_case_blocks(case_block, domain=self.domain)[0].form_id

        # validate that worked
        case = self.casedb.get_case(case_id)
        self.assertEqual([create_form_id], case.xform_ids)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertTrue(create_form_id in [a.xform_id for a in case.actions])
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
        ).as_string().decode('utf-8')
        edit_form_id = submit_case_blocks(case_block, domain=self.domain)[0].form_id

        # validate that worked
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties()['property'], 'first value')
        self.assertEqual([create_form_id, edit_form_id], case.xform_ids)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertTrue(all(
                form_id in [a.xform_id for a in case.actions]
                for form_id in [create_form_id, edit_form_id]
            ))

        # submit a second (new) form updating the value
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            update={
                'property': 'final value',
            }
        ).as_string().decode('utf-8')
        second_edit_form_id = submit_case_blocks(case_block, domain=self.domain)[0].form_id

        # validate that worked
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties()['property'], 'final value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertTrue(all(
                form_id in [a.xform_id for a in case.actions]
                for form_id in [create_form_id, edit_form_id, second_edit_form_id]
            ))

        # deprecate the middle edit
        case_block = CaseBlock(
            create=False,
            case_id=case_id,
            date_modified=edit_date,  # need to use the previous edit date for action sort comparisons
            update={
                'property': 'edited value',
                'added_property': 'added value',
            }
        ).as_string().decode('utf-8')
        submit_case_blocks(case_block, domain=self.domain, form_id=edit_form_id)

        # ensure that the middle edit stays in the right place and is applied
        # before the final one
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties()['property'], 'final value')
        self.assertEqual(case.dynamic_case_properties()['added_property'], 'added value')
        self.assertEqual([create_form_id, edit_form_id, second_edit_form_id], case.xform_ids)

        if not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(
                [create_form_id, create_form_id, edit_form_id, second_edit_form_id],
                [a.xform_id for a in case.actions]
            )

    def test_edit_different_xmlns(self):
        form_id = uuid.uuid4().hex
        case1_id = uuid.uuid4().hex
        case2_id = uuid.uuid4().hex
        xmlns1 = 'http://commcarehq.org/xmlns1'
        xmlns2 = 'http://commcarehq.org/xmlns2'

        case_block = CaseBlock(
            create=True,
            case_id=case1_id,
            case_type='person',
            owner_id='owner1',
        ).as_string().decode('utf-8')
        xform, cases = submit_case_blocks(case_block, domain=self.domain, xmlns=xmlns1, form_id=form_id)

        self.assertTrue(xform.is_normal)
        self.assertEqual(form_id, xform.form_id)

        case_block = CaseBlock(
            create=True,
            case_id=case2_id,
            case_type='goat',
            owner_id='owner1',
        ).as_string().decode('utf-8')
        # submit new form with same form ID but different XMLNS
        xform, cases = submit_case_blocks(case_block, domain=self.domain, xmlns=xmlns2, form_id=form_id)

        self.assertTrue(xform.is_normal)
        self.assertNotEqual(form_id, xform.form_id)  # form should have a different ID

    def test_copy_operations(self):
        original_xml = self.get_xml('original')
        edit_xml = self.get_xml('edit')

        xform = submit_form_locally(original_xml, self.domain).xform
        xform.archive(user_id='user1')
        xform.unarchive(user_id='user2')

        xform = submit_form_locally(edit_xml, self.domain).xform
        self.assertEqual(3, len(xform.history))
        self.assertEqual('archive', xform.history[0].operation)
        self.assertEqual('unarchive', xform.history[1].operation)
        self.assertEqual('edit', xform.history[2].operation)


@use_sql_backend
class EditFormTestSQL(EditFormTest):
    pass
