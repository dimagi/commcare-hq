from __future__ import absolute_import
import uuid
from datetime import datetime

from contextlib2 import ExitStack
from django.core.files.uploadedfile import UploadedFile
from django.test import TestCase

import settings
from corehq.blobs import get_blob_db
from corehq.blobs.tests.util import TemporaryS3BlobDB, TemporaryFilesystemBlobDB
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import XFormNotFound, AttachmentNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import (
    XFormInstanceSQL, XFormOperationSQL, XFormAttachmentSQL
)
from corehq.form_processor.parsers.form import apply_deprecation
from corehq.form_processor.tests.utils import (
    create_form_for_test, FormProcessorTestUtils, use_sql_backend
)
from corehq.form_processor.utils import get_simple_form_xml, get_simple_wrapped_form
from corehq.form_processor.utils.xform import TestFormMetadata
from corehq.sql_db.routers import db_for_read_write
from corehq.util.test_utils import trap_extra_setup

DOMAIN = 'test-form-accessor'


@use_sql_backend
class FormAccessorTestsSQL(TestCase):

    def tearDown(self):
        FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
        FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super(FormAccessorTestsSQL, self).tearDown()

    def test_get_form_by_id(self):
        form = create_form_for_test(DOMAIN)
        with self.assertNumQueries(1, using=form.db):
            form = FormAccessorSQL.get_form(form.form_id)
        self._check_simple_form(form)

    def test_get_form_by_id_missing(self):
        with self.assertRaises(XFormNotFound):
            FormAccessorSQL.get_form('missing_form')

    def test_get_forms(self):
        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN)

        forms = FormAccessorSQL.get_forms(['missing_form'])
        self.assertEqual(0, len(forms))

        forms = FormAccessorSQL.get_forms([form1.form_id])
        self.assertEqual(1, len(forms))
        self.assertEqual(form1.form_id, forms[0].form_id)

        forms = FormAccessorSQL.get_forms([form1.form_id, form2.form_id], ordered=True)
        self.assertEqual(2, len(forms))
        self.assertEqual(form1.form_id, forms[0].form_id)
        self.assertEqual(form2.form_id, forms[1].form_id)

    def test_get_forms_by_last_modified(self):
        start = datetime(2016, 1, 1)
        end = datetime(2018, 1, 1)

        form1 = create_form_for_test(DOMAIN, received_on=datetime(2017, 1, 1))
        create_form_for_test(DOMAIN, received_on=datetime(2015, 1, 1))
        # Test that it gets all states
        form2 = create_form_for_test(
            DOMAIN,
            state=XFormInstanceSQL.ARCHIVED,
            received_on=datetime(2017, 1, 1)
        )
        # Test that other date fields are properly fetched
        form3 = create_form_for_test(
            DOMAIN,
            received_on=datetime(2015, 1, 1),
            edited_on=datetime(2017, 1, 1),
        )

        forms = list(FormAccessorSQL.iter_forms_by_last_modified(start, end))
        self.assertEqual(3, len(forms))
        self.assertEqual(
            {form1.form_id, form2.form_id, form3.form_id},
            {form.form_id for form in forms},
        )

    def test_get_with_attachments(self):
        form = create_form_for_test(DOMAIN)
        with self.assertNumQueries(1, using=db_for_read_write(XFormAttachmentSQL)):
            form.get_attachment_meta('form.xml')

        with ExitStack() as stack:
            if settings.USE_PARTITIONED_DATABASE:
                proxy_queries = 1
                stack.enter_context(self.assertNumQueries(1, using=form.db))
            else:
                proxy_queries = 2
            stack.enter_context(self.assertNumQueries(proxy_queries, using=db_for_read_write(XFormAttachmentSQL)))
            form = FormAccessorSQL.get_with_attachments(form.form_id)

        self._check_simple_form(form)
        with self.assertNumQueries(0, using=db_for_read_write(XFormAttachmentSQL)):
            attachment_meta = form.get_attachment_meta('form.xml')

        self.assertEqual(form.form_id, attachment_meta.form_id)
        self.assertEqual('form.xml', attachment_meta.name)
        self.assertEqual('text/xml', attachment_meta.content_type)

    def test_get_attachment_by_name(self):
        form = create_form_for_test(DOMAIN)
        form_xml = get_simple_form_xml(form.form_id)

        with self.assertRaises(AttachmentNotFound):
            FormAccessorSQL.get_attachment_by_name(form.form_id, 'not_a_form.xml')

        with self.assertNumQueries(1, using=db_for_read_write(XFormAttachmentSQL)):
            attachment_meta = FormAccessorSQL.get_attachment_by_name(form.form_id, 'form.xml')

        self.assertEqual(form.form_id, attachment_meta.form_id)
        self.assertEqual('form.xml', attachment_meta.name)
        self.assertEqual('text/xml', attachment_meta.content_type)
        self.assertEqual(form_xml, attachment_meta.read_content())

    def test_get_form_operations(self):
        form = create_form_for_test(DOMAIN)

        operations = FormAccessorSQL.get_form_operations('missing_form')
        self.assertEqual([], operations)

        operations = FormAccessorSQL.get_form_operations(form.form_id)
        self.assertEqual([], operations)

        # don't call form.archive to avoid sending the signals
        FormAccessorSQL.archive_form(form, user_id='user1')
        FormAccessorSQL.unarchive_form(form, user_id='user2')

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
        form_with_pic = create_form_for_test(DOMAIN, attachments=attachments)
        plain_form = create_form_for_test(DOMAIN)

        forms = FormAccessorSQL.get_forms_with_attachments_meta(
            [form_with_pic.form_id, plain_form.form_id], ordered=True
        )
        self.assertEqual(2, len(forms))
        form = forms[0]
        self.assertEqual(form_with_pic.form_id, form.form_id)
        with self.assertNumQueries(0, using=db_for_read_write(XFormAttachmentSQL)):
            expected = {
                'form.xml': 'text/xml',
                'pic.jpg': 'image/jpeg',
            }
            attachments = form.get_attachments()
            self.assertEqual(2, len(attachments))
            self.assertEqual(expected, {att.name: att.content_type for att in attachments})

        with self.assertNumQueries(0, using=db_for_read_write(XFormAttachmentSQL)):
            expected = {
                'form.xml': 'text/xml',
            }
            attachments = forms[1].get_attachments()
            self.assertEqual(1, len(attachments))
            self.assertEqual(expected, {att.name: att.content_type for att in attachments})

    def test_get_form_ids_in_domain(self):

        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN)
        create_form_for_test('bad-domain')

        # basic check
        form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(DOMAIN, 'XFormInstance')
        self.assertEqual(2, len(form_ids))
        self.assertEqual({form1.form_id, form2.form_id}, set(form_ids))

        # change state of form1
        FormAccessorSQL.archive_form(form1, 'user1')

        # check filtering by state
        form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(DOMAIN, 'XFormArchived')
        self.assertEqual(1, len(form_ids))
        self.assertEqual(form1.form_id, form_ids[0])

        form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(DOMAIN, 'XFormInstance')
        self.assertEqual(1, len(form_ids))
        self.assertEqual(form2.form_id, form_ids[0])

    def test_get_forms_by_type(self):
        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN)

        # basic check
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 5)
        self.assertEqual(2, len(forms))
        self.assertEqual({form1.form_id, form2.form_id}, {f.form_id for f in forms})

        # check reverse ordering
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 5, recent_first=True)
        self.assertEqual(2, len(forms))
        self.assertEqual([form2.form_id, form1.form_id], [f.form_id for f in forms])

        # check limit
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 1)
        self.assertEqual(1, len(forms))
        self.assertEqual(form1.form_id, forms[0].form_id)

        # change state of form1
        FormAccessorSQL.archive_form(form1, 'user1')

        # check filtering by state
        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormArchived', 2)
        self.assertEqual(1, len(forms))
        self.assertEqual(form1.form_id, forms[0].form_id)

        forms = FormAccessorSQL.get_forms_by_type(DOMAIN, 'XFormInstance', 2)
        self.assertEqual(1, len(forms))
        self.assertEqual(form2.form_id, forms[0].form_id)

    def test_form_with_id_exists(self):
        form = create_form_for_test(DOMAIN)

        self.assertFalse(FormAccessorSQL.form_exists('not a form'))
        self.assertFalse(FormAccessorSQL.form_exists(form.form_id, 'wrong domain'))
        self.assertTrue(FormAccessorSQL.form_exists(form.form_id))
        self.assertTrue(FormAccessorSQL.form_exists(form.form_id, DOMAIN))

    def test_hard_delete_forms(self):
        forms = [create_form_for_test(DOMAIN) for i in range(3)]
        form_ids = [form.form_id for form in forms]
        other_form = create_form_for_test('other_domain')
        self.addCleanup(lambda: FormAccessorSQL.hard_delete_forms('other_domain', [other_form.form_id]))
        forms = FormAccessorSQL.get_forms(form_ids)
        self.assertEqual(3, len(forms))

        deleted = FormAccessorSQL.hard_delete_forms(DOMAIN, form_ids[1:] + [other_form.form_id])
        self.assertEqual(2, deleted)
        forms = FormAccessorSQL.get_forms(form_ids)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_ids[0], forms[0].form_id)

    def test_archive_unarchive_form(self):
        case_id = uuid.uuid4().hex
        form = create_form_for_test(DOMAIN, case_id=case_id)
        self.assertEqual(XFormInstanceSQL.NORMAL, form.state)
        self.assertEqual(0, len(form.history))

        transactions = CaseAccessorSQL.get_transactions(case_id)
        self.assertEqual(1, len(transactions))
        self.assertFalse(transactions[0].revoked)

        FormAccessorSQL.archive_form(form, 'user1')
        form = FormAccessorSQL.get_form(form.form_id)
        self.assertEqual(XFormInstanceSQL.ARCHIVED, form.state)
        operations = form.history
        self.assertEqual(1, len(operations))
        self.assertEqual(form.form_id, operations[0].form_id)
        self.assertEqual('user1', operations[0].user_id)

        transactions = CaseAccessorSQL.get_transactions(case_id)
        self.assertEqual(1, len(transactions))
        self.assertTrue(transactions[0].revoked)

        FormAccessorSQL.unarchive_form(form, 'user2')
        form = FormAccessorSQL.get_form(form.form_id)
        self.assertEqual(XFormInstanceSQL.NORMAL, form.state)
        operations = form.history
        self.assertEqual(2, len(operations))
        self.assertEqual(form.form_id, operations[1].form_id)
        self.assertEqual('user2', operations[1].user_id)

        transactions = CaseAccessorSQL.get_transactions(case_id)
        self.assertEqual(1, len(transactions))
        self.assertFalse(transactions[0].revoked)

    def test_save_new_form(self):
        unsaved_form = create_form_for_test(DOMAIN, save=False)
        FormAccessorSQL.save_new_form(unsaved_form)
        self.assertTrue(unsaved_form.is_saved())

        attachments = FormAccessorSQL.get_attachments(unsaved_form.form_id)
        self.assertEqual(1, len(attachments))

    def test_save_form_db_error(self):
        form = create_form_for_test(DOMAIN)
        dup_form = create_form_for_test(DOMAIN, save=False)
        dup_form.form_id = form.form_id

        try:
            FormAccessorSQL.save_new_form(dup_form)
        except Exception:
            dup_form.form_id = uuid.uuid4().hex
            FormAccessorSQL.save_new_form(dup_form)
        else:
            self.fail("saving dup form didn't raise an exception")

        attachments = FormAccessorSQL.get_attachments(dup_form.form_id)
        self.assertEqual(1, len(attachments))

    def test_save_form_deprecated(self):
        existing_form, new_form = _simulate_form_edit()

        FormAccessorSQL.update_form(existing_form, publish_changes=False)
        FormAccessorSQL.save_new_form(new_form)

        self._validate_deprecation(existing_form, new_form)

    def test_save_processed_models_deprecated(self):
        existing_form, new_form = _simulate_form_edit()

        FormProcessorSQL.save_processed_models(ProcessedForms(new_form, existing_form))

        self._validate_deprecation(existing_form, new_form)

    def test_update_form_problem_and_state(self):
        form = create_form_for_test(DOMAIN)
        self.assertEqual(XFormInstanceSQL.NORMAL, form.state)

        original_domain = form.domain
        problem = 'Houston, we have a problem'
        form.state = XFormInstanceSQL.ERROR
        form.problem = problem
        form.domain = 'new domain'  # shouldn't get saved
        FormAccessorSQL.update_form_problem_and_state(form)

        saved_form = FormAccessorSQL.get_form(form.form_id)
        self.assertEqual(XFormInstanceSQL.ERROR, saved_form.state)
        self.assertEqual(problem, saved_form.problem)
        self.assertEqual(original_domain, saved_form.domain)

    def _validate_deprecation(self, existing_form, new_form):
        saved_new_form = FormAccessorSQL.get_form(new_form.form_id)
        deprecated_form = FormAccessorSQL.get_form(existing_form.form_id)
        self.assertEqual(deprecated_form.form_id, saved_new_form.deprecated_form_id)
        self.assertTrue(deprecated_form.is_deprecated)
        self.assertNotEqual(saved_new_form.form_id, deprecated_form.form_id)
        self.assertEqual(saved_new_form.form_id, deprecated_form.orig_id)

    def _check_simple_form(self, form):
        self.assertIsInstance(form, XFormInstanceSQL)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
        return form


class FormAccessorsTests(TestCase):

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        super(FormAccessorsTests, self).tearDown()

    def test_soft_delete(self):
        meta = TestFormMetadata(domain=DOMAIN)
        get_simple_wrapped_form('f1', metadata=meta)
        f2 = get_simple_wrapped_form('f2', metadata=meta)
        f2.archive()
        get_simple_wrapped_form('f3', metadata=meta)

        accessors = FormAccessors(DOMAIN)

        # delete
        num = accessors.soft_delete_forms(['f1', 'f2'], deletion_id='123')
        self.assertEqual(num, 2)

        for form_id in ['f1', 'f2']:
            form = accessors.get_form(form_id)
            self.assertTrue(form.is_deleted)
            self.assertEqual(form.deletion_id, '123')

        form = accessors.get_form('f3')
        self.assertFalse(form.is_deleted)

        for form_id in ['f1', 'f2']:
            form = FormAccessors(DOMAIN).get_form(form_id)
            form.delete()


@use_sql_backend
class FormAccessorsTestsSQL(FormAccessorsTests):
    pass


class DeleteAttachmentsFSDBTests(TestCase):
    def setUp(self):
        super(DeleteAttachmentsFSDBTests, self).setUp()
        self.db = TemporaryFilesystemBlobDB()

    def tearDown(self):
        self.db.close()
        super(DeleteAttachmentsFSDBTests, self).tearDown()

    def test_hard_delete_forms_and_attachments(self):
        forms = [create_form_for_test(DOMAIN) for i in range(3)]
        form_ids = [form.form_id for form in forms]
        forms = FormAccessorSQL.get_forms(form_ids)
        self.assertEqual(3, len(forms))

        other_form = create_form_for_test('other_domain')
        self.addCleanup(lambda: FormAccessorSQL.hard_delete_forms('other_domain', [other_form.form_id]))

        attachments = list(FormAccessorSQL.get_attachments_for_forms(form_ids, ordered=True))
        self.assertEqual(3, len(attachments))

        deleted = FormAccessorSQL.hard_delete_forms(DOMAIN, form_ids[1:] + [other_form.form_id])
        self.assertEqual(2, deleted)

        forms = FormAccessorSQL.get_forms(form_ids)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_ids[0], forms[0].form_id)

        for attachment in attachments[1:]:
            with self.assertRaises(AttachmentNotFound):
                attachment.read_content()

        self.assertIsNotNone(attachments[0].read_content())
        other_form = FormAccessorSQL.get_form(other_form.form_id)
        self.assertIsNotNone(other_form.get_xml())


class DeleteAtachmentsS3DBTests(DeleteAttachmentsFSDBTests):
    def setUp(self):
        super(DeleteAtachmentsS3DBTests, self).setUp()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS

        self.s3db = TemporaryS3BlobDB(config)
        assert get_blob_db() is self.s3db, (get_blob_db(), self.s3db)

    def tearDown(self):
        self.s3db.close()
        super(DeleteAtachmentsS3DBTests, self).tearDown()



def _simulate_form_edit():
    existing_form = create_form_for_test(DOMAIN, save=False)
    FormAccessorSQL.save_new_form(existing_form)
    existing_form = FormAccessorSQL.get_form(existing_form.form_id)

    new_form = create_form_for_test(DOMAIN, save=False)
    new_form.form_id = existing_form.form_id

    existing_form, new_form = apply_deprecation(existing_form, new_form)
    assert existing_form.form_id != new_form.form_id
    return existing_form, new_form
