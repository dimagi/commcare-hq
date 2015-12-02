import uuid

from datetime import datetime
from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import XFormNotFound, AttachmentNotFound
from corehq.form_processor.models import XFormInstanceSQL, XFormOperationSQL, Attachment, CommCareCaseSQL, \
    CaseTransaction
from crispy_forms.tests.utils import override_settings

DOMAIN = 'test-form-accessor'

SIMPLE_FORM = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="New Form" xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
    xmlns="http://openrosa.org/formdesigner/form-processor">
    <dalmation_count>yes</dalmation_count>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>DEV IL</n1:deviceID>
        <n1:timeStart>2013-04-19T16:52:41.000-04</n1:timeStart>
        <n1:timeEnd>2013-04-19T16:53:02.799-04</n1:timeEnd>
        <n1:username>eve</n1:username>
        <n1:userID>cruella_deville</n1:userID>
        <n1:instanceID>{uuid}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms"></n2:appVersion>
    </n1:meta>
    {case_block}
</data>"""


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class FormProcessorSQLTests(TestCase):
    dependent_apps = []

    def test_save_form(self):
        unsaved_form = _create_form()
        FormProcessorSQL.save_xform(unsaved_form)
        self.assertTrue(unsaved_form.is_saved())

        attachments = FormAccessorSQL.get_attachments(unsaved_form.form_id)
        self.assertEqual(1, len(attachments))

    def test_save_form_deprecated(self):
        existing_form = _create_form()
        FormProcessorSQL.save_xform(existing_form)
        existing_form = FormAccessorSQL.get_form(existing_form.form_id)

        new_form = _create_form()
        new_form.form_id = existing_form.form_id

        FormProcessorSQL.apply_deprecation(existing_form, new_form)
        self.assertNotEqual(existing_form.form_id, new_form.form_id)

        FormProcessorSQL.save_xform(existing_form, is_deprecation=True)
        deprecated_form = FormAccessorSQL.get_form(existing_form.form_id)
        self.assertTrue(deprecated_form.is_deprecated)
        self.assertNotEqual(new_form.form_id, deprecated_form.form_id)
        self.assertEqual(new_form.form_id, deprecated_form.orig_id)

    def test_save_processed_models_deprecated(self):
        existing_form = _create_form()
        FormProcessorSQL.save_xform(existing_form)
        existing_form = FormAccessorSQL.get_form(existing_form.form_id)

        new_form = _create_form()
        new_form.form_id = existing_form.form_id

        FormProcessorSQL.apply_deprecation(existing_form, new_form)
        self.assertNotEqual(existing_form.form_id, new_form.form_id)

        FormProcessorSQL.save_processed_models([new_form, existing_form])


def _create_form(case_id=None, attachments=None):
    form_id = uuid.uuid4().hex
    user_id = 'user1'
    utcnow = datetime.utcnow()

    form_data = _get_form_data(form_id, case_id)

    unsaved_form = XFormInstanceSQL(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=DOMAIN
    )

    attachments = attachments or {}
    attachment_tuples = map(
        lambda a: Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachment_tuples.append(Attachment('form.xml', form_data, 'text/xml'))

    FormProcessorSQL.store_attachments(unsaved_form, attachment_tuples)
    return unsaved_form


def _get_form_data(form_id, case_id=None):
    case_block = ''
    if case_id:
        case_block = CaseBlock(create=True, case_id=case_id).as_string()
    form_data = SIMPLE_FORM.format(uuid=form_id, case_block=case_block)
    return form_data
