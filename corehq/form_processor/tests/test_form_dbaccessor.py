import uuid

from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.exceptions import XFormNotFound, AttachmentNotFound
from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL
from crispy_forms.tests.utils import override_settings

DOMAIN = 'test-form-accessor'

SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="New Form" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="http://openrosa.org/formdesigner/1DFD8610-91E3-4409-BF8B-02D3B4FF3530">
    <dalmation_count>yes</dalmation_count>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>DEV IL</n1:deviceID>
        <n1:timeStart>2013-04-19T16:52:41.000-04</n1:timeStart>
        <n1:timeEnd>2013-04-19T16:53:02.799-04</n1:timeEnd>
        <n1:username>eve</n1:username>
        <n1:userID>cruella_deville</n1:userID>
        <n1:instanceID>{}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms"></n2:appVersion>
    </n1:meta>
</data>"""


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class FormAccessorTests(TestCase):

    def test_get_form_by_id(self):
        form_id = _submit_simple_form()
        with self.assertNumQueries(1):
            form = FormAccessorSQL.get_form(form_id)
        self._check_simple_form(form)

    def test_get_form_by_id_missing(self):
        with self.assertRaises(XFormNotFound):
            FormAccessorSQL.get_form('missing_form')

    def test_get_forms(self):
        form_id1 = _submit_simple_form()
        form_id2 = _submit_simple_form()

        forms = FormAccessorSQL.get_forms(['missing_form'])
        self.assertEqual([], forms)

        forms = FormAccessorSQL.get_forms([form_id1])
        self.assertEqual(1, len(forms))
        self.assertEqual(form_id1, forms[0].form_id)

        forms = FormAccessorSQL.get_forms([form_id1, form_id2], ordered=True)
        self.assertEqual(2, len(forms))
        self.assertEqual(form_id1, forms[0].form_id)
        self.assertEqual(form_id2, forms[1].form_id)

    def test_get_with_attachments(self):
        form_id = _submit_simple_form()
        form = FormAccessorSQL.get_form(form_id)
        with self.assertNumQueries(1):
            form.get_attachment_meta('form.xml')

        with self.assertNumQueries(2):
            form = FormAccessorSQL.get_with_attachments(form_id)

        self._check_simple_form(form)
        with self.assertNumQueries(0):
            attachment_meta = form.get_attachment_meta('form.xml')

        self.assertEqual(form_id, attachment_meta.form_id)
        self.assertEqual('form.xml', attachment_meta.name)
        self.assertEqual('text/xml', attachment_meta.content_type)

    def test_get_attachment_by_name(self):
        form_xml = SIMPLE_FORM.format(uuid.uuid4().hex)
        _, form, _ = submit_form_locally(
            instance=form_xml,
            domain=DOMAIN,
        )

        with self.assertRaises(AttachmentNotFound):
            a = FormAccessorSQL.get_attachment_by_name(form.form_id, 'not_a_form.xml')
            print a.name, a.form_id, a.content_type

        with self.assertNumQueries(1):
            attachment_meta = FormAccessorSQL.get_attachment_by_name(form.form_id, 'form.xml')

        self.assertEqual(form.form_id, attachment_meta.form_id)
        self.assertEqual('form.xml', attachment_meta.name)
        self.assertEqual('text/xml', attachment_meta.content_type)
        self.assertEqual(form_xml, attachment_meta.read_content())

    def test_get_form_operations(self):
        _, form, _ = submit_form_locally(
            instance=SIMPLE_FORM.format(uuid.uuid4().hex),
            domain=DOMAIN,
        )

        operations = FormAccessorSQL.get_form_operations('missing_form')
        self.assertEqual([], operations)

        operations = FormAccessorSQL.get_form_operations(form.form_id)
        self.assertEqual([], operations)

        # don't call form.archive to avoid sending the signals
        FormAccessorSQL.archive_form(form.form_id, user_id='user1')
        FormAccessorSQL.unarchive_form(form.form_id, user_id='user2')

        operations = FormAccessorSQL.get_form_operations(form.form_id)
        self.assertEqual(2, len(operations))
        self.assertEqual('user1', operations[0].user_id)
        self.assertEqual(XFormOperationSQL.ARCHIVE, operations[0].operation)
        self.assertIsNotNone(operations[0].date)
        self.assertEqual('user2', operations[1].user_id)
        self.assertEqual(XFormOperationSQL.UNARCHIVE, operations[1].operation)
        self.assertIsNotNone(operations[1].date)
        self.assertGreater(operations[1].date, operations[0].date)

    def test_get_forms_with_attachments_meta(self):
        attachment_file = open('./corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg', 'rb')
        attachments = {
            'pic.jpg': UploadedFile(attachment_file, 'pic.jpg', content_type='image/jpeg')
        }
        _, form_with_pic, _ = submit_form_locally(
            instance=SIMPLE_FORM.format(uuid.uuid4().hex),
            domain=DOMAIN,
            attachments=attachments
        )
        _, plain_form, _ = submit_form_locally(
            instance=SIMPLE_FORM.format(uuid.uuid4().hex),
            domain=DOMAIN,
        )

        forms = FormAccessorSQL.get_forms_with_attachments_meta([form_with_pic.form_id, plain_form.form_id])
        self.assertEqual(2, len(forms))
        self.assertEqual(form_with_pic.form_id, forms[0].form_id)
        with self.assertNumQueries(0):
            expected = {
                'form.xml': 'text/xml',
                'pic.jpg': 'image/jpeg',
            }
            attachments = forms[0].get_attachments()
            self.assertEqual(2, len(attachments))
            self.assertEqual(expected, {att.name: att.content_type for att in attachments})

        with self.assertNumQueries(0):
            expected = {
                'form.xml': 'text/xml',
            }
            attachments = forms[1].get_attachments()
            self.assertEqual(1, len(attachments))
            self.assertEqual(expected, {att.name: att.content_type for att in attachments})

    def test_get_forms_by_type(self):
        form_id1 = _submit_simple_form()
        form_id2 = _submit_simple_form()

        # basic check
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 5)
        self.assertEqual(2, len(forms))
        self.assertEqual([form_id1, form_id2], [f.form_id for f in forms])

        # check reverse ordering
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 5, recent_first=True)
        self.assertEqual(2, len(forms))
        self.assertEqual([form_id2, form_id1], [f.form_id for f in forms])

        # check limit
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 1)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_id1, forms[0].form_id)

        # change state of form1
        FormAccessorSQL.archive_form(form_id1, 'user1')

        # check filtering by state
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormArchived', 2)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_id1, forms[0].form_id)

        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 2)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_id2, forms[0].form_id)

    def _check_simple_form(self, form):
        self.assertIsInstance(form, XFormInstanceSQL)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
        return form


def _submit_simple_form():
    case_id = uuid.uuid4().hex
    return submit_case_blocks(
        CaseBlock(create=True, case_id=case_id).as_string(),
        domain=DOMAIN,
        user_id='user1',
    )
