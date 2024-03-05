import uuid
from datetime import datetime

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.test import SimpleTestCase, TestCase

from corehq.blobs import NotFound as BlobNotFound, get_blob_db
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, TemporaryS3BlobDB
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
from corehq.util.test_utils import trap_extra_setup

from ..backends.sql.processor import FormProcessorSQL
from ..exceptions import AttachmentNotFound, XFormNotFound
from ..interfaces.processor import ProcessedForms
from ..models import CaseTransaction, XFormInstance, XFormOperation
from ..models.forms import TempFormCache
from ..tests.utils import FormProcessorTestUtils, create_form_for_test, sharded
from ..parsers.form import apply_deprecation
from ..utils import get_simple_form_xml, get_simple_wrapped_form
from ..utils.xform import TestFormMetadata

DOMAIN = 'test-forms-manager'


@sharded
class XFormInstanceManagerTest(TestCase):

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
            FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super().tearDown()

    def test_get_form(self):
        form = create_form_for_test(DOMAIN)
        with self.assertNumQueries(1, using=form.db):
            form = XFormInstance.objects.get_form(form.form_id, DOMAIN)
        self._check_simple_form(form)

    def test_get_form_with_wrong_domain(self):
        form = create_form_for_test(DOMAIN)
        with self.assertRaises(XFormNotFound):
            XFormInstance.objects.get_form(form.form_id, "wrong-domain")

    def test_get_form_without_domain(self):
        # DEPRECATED domain should be supplied if available
        form = create_form_for_test(DOMAIN)
        with self.assertNumQueries(1, using=form.db):
            form = XFormInstance.objects.get_form(form.form_id)
        self._check_simple_form(form)

    def test_get_form_missing(self):
        with self.assertRaises(XFormNotFound):
            XFormInstance.objects.get_form('missing_form')

    def test_form_exists(self):
        form = create_form_for_test(DOMAIN)
        form_exists = XFormInstance.objects.form_exists

        self.assertFalse(form_exists('not a form'))
        self.assertFalse(form_exists(form.form_id, 'wrong domain'))
        self.assertTrue(form_exists(form.form_id))
        self.assertTrue(form_exists(form.form_id, DOMAIN))

    def test_get_forms(self):
        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN)

        forms = XFormInstance.objects.get_forms(['missing_form'])
        self.assertEqual(forms, [])

        forms = XFormInstance.objects.get_forms([form1.form_id])
        self.assertEqual([f.form_id for f in forms], [form1.form_id])

        forms = XFormInstance.objects.get_forms([form1.form_id, form2.form_id], ordered=True)
        self.assertEqual([f.form_id for f in forms], [form1.form_id, form2.form_id])

    def test_get_with_attachments(self):
        form = create_form_for_test(DOMAIN)
        form = XFormInstance.objects.get_form(form.form_id)  # refetch to clear cached attachments
        form_db = get_db_alias_for_partitioned_doc(form.form_id)
        with self.assertNumQueries(1, using=form_db):
            form.get_attachment_meta('form.xml')

        with self.assertNumQueries(1, using=form_db):
            form.get_attachment_meta('form.xml')

        with self.assertNumQueries(2, using=form_db):
            form = XFormInstance.objects.get_with_attachments(form.form_id)

        self._check_simple_form(form)
        with self.assertNumQueries(0, using=form_db):
            attachment_meta = form.get_attachment_meta('form.xml')

        self.assertEqual(form.form_id, attachment_meta.parent_id)
        self.assertEqual('form.xml', attachment_meta.name)
        self.assertEqual('text/xml', attachment_meta.content_type)

    def test_get_attachment_by_name(self):
        form = create_form_for_test(DOMAIN)
        form_xml = get_simple_form_xml(form.form_id)
        form_db = get_db_alias_for_partitioned_doc(form.form_id)
        get_attachment = XFormInstance.objects.get_attachment_by_name

        with self.assertRaises(AttachmentNotFound):
            get_attachment(form.form_id, 'not_a_form.xml')

        with self.assertNumQueries(1, using=form_db):
            attachment_meta = get_attachment(form.form_id, 'form.xml')

        self.assertEqual(form.form_id, attachment_meta.parent_id)
        self.assertEqual('form.xml', attachment_meta.name)
        self.assertEqual('text/xml', attachment_meta.content_type)
        with attachment_meta.open() as content:
            self.assertEqual(form_xml, content.read().decode('utf-8'))

    def test_get_forms_with_attachments_meta(self):
        attachment_file = open('./corehq/ex-submodules/casexml/apps/case/tests/data/attachments/fruity.jpg', 'rb')
        attachments = {
            'pic.jpg': UploadedFile(attachment_file, 'pic.jpg', content_type='image/jpeg')
        }
        form_with_pic = create_form_for_test(DOMAIN, attachments=attachments)
        plain_form = create_form_for_test(DOMAIN)

        forms = XFormInstance.objects.get_forms_with_attachments_meta(
            [form_with_pic.form_id, plain_form.form_id], ordered=True
        )
        self.assertEqual(2, len(forms))
        form = forms[0]
        self.assertEqual(form_with_pic.form_id, form.form_id)
        with self.assertNumQueries(0, using=form.db):
            expected = {
                'form.xml': 'text/xml',
                'pic.jpg': 'image/jpeg',
            }
            attachments = form.get_attachments()
            self.assertEqual(2, len(attachments))
            self.assertEqual(expected, {att.name: att.content_type for att in attachments})

        with self.assertNumQueries(0, using=forms[1].db):
            expected = {
                'form.xml': 'text/xml',
            }
            attachments = forms[1].get_attachments()
            self.assertEqual(1, len(attachments))
            self.assertEqual(expected, {att.name: att.content_type for att in attachments})

    def test_get_forms_by_type(self):
        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN)

        # basic check
        forms = XFormInstance.objects.get_forms_by_type(DOMAIN, 'XFormInstance', 5)
        self.assertEqual(2, len(forms))
        self.assertEqual({form1.form_id, form2.form_id}, {f.form_id for f in forms})

        # check reverse ordering
        forms = XFormInstance.objects.get_forms_by_type(DOMAIN, 'XFormInstance', 5, recent_first=True)
        self.assertEqual(2, len(forms))
        self.assertEqual([form2.form_id, form1.form_id], [f.form_id for f in forms])

        # check limit
        forms = XFormInstance.objects.get_forms_by_type(DOMAIN, 'XFormInstance', 1)
        self.assertEqual(1, len(forms))
        self.assertEqual(form1.form_id, forms[0].form_id)

        # change state of form1
        archive_form(form1, 'user1')

        # check filtering by state
        forms = XFormInstance.objects.get_forms_by_type(DOMAIN, 'XFormArchived', 2)
        self.assertEqual(1, len(forms))
        self.assertEqual(form1.form_id, forms[0].form_id)

        forms = XFormInstance.objects.get_forms_by_type(DOMAIN, 'XFormInstance', 2)
        self.assertEqual(1, len(forms))
        self.assertEqual(form2.form_id, forms[0].form_id)

    def test_get_form_ids_in_domain(self):
        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN)
        create_form_for_test('bad-domain')

        # basic check
        form_ids = XFormInstance.objects.get_form_ids_in_domain(DOMAIN)
        self.assertEqual(set(form_ids), {form1.form_id, form2.form_id})

        # change state of form1
        archive_form(form1, 'user1')

        # check filtering by state
        form_ids = XFormInstance.objects.get_form_ids_in_domain(DOMAIN, 'XFormArchived')
        self.assertEqual(form_ids, [form1.form_id])

        form_ids = XFormInstance.objects.get_form_ids_in_domain(DOMAIN, 'XFormInstance')
        self.assertEqual(form_ids, [form2.form_id])

    def test_iter_form_ids_by_xmlns(self):
        OTHER_XMLNS = "http://openrosa.org/other"
        form1 = create_form_for_test(DOMAIN)
        form2 = create_form_for_test(DOMAIN, xmlns=OTHER_XMLNS)

        ids = XFormInstance.objects.iter_form_ids_by_xmlns("nonexistent")
        self.assertFalse(list(ids))

        ids = XFormInstance.objects.iter_form_ids_by_xmlns(DOMAIN, "unknown-xmlns")
        self.assertFalse(list(ids))

        ids = XFormInstance.objects.iter_form_ids_by_xmlns(DOMAIN, OTHER_XMLNS)
        self.assertEqual(list(ids), [form2.form_id])

        ids = XFormInstance.objects.iter_form_ids_by_xmlns(DOMAIN)
        self.assertEqual(set(ids), {form1.form_id, form2.form_id})

    def test_archive_unarchive_form(self):
        case_id = uuid.uuid4().hex
        form = create_form_for_test(DOMAIN, case_id=case_id)
        self.assertEqual(XFormInstance.NORMAL, form.state)
        self.assertEqual(0, len(form.history))

        transactions = CaseTransaction.objects.get_transactions(case_id)
        self.assertEqual(1, len(transactions))
        self.assertFalse(transactions[0].revoked)

        # archive twice to check that it's idempotent
        for i in range(2):
            archive_form(form, 'user1')
            form = XFormInstance.objects.get_form(form.form_id)
            self.assertEqual(XFormInstance.ARCHIVED, form.state)
            operations = form.history
            self.assertEqual(i + 1, len(operations))
            self.assertEqual(form.form_id, operations[i].form_id)
            self.assertEqual('user1', operations[i].user_id)

            transactions = CaseTransaction.objects.get_transactions(case_id)
            self.assertEqual(1, len(transactions), transactions)
            self.assertTrue(transactions[0].revoked)

        # unarchive twice to check that it's idempotent
        for i in range(2, 4):
            unarchive_form(form, 'user2')
            form = XFormInstance.objects.get_form(form.form_id)
            self.assertEqual(XFormInstance.NORMAL, form.state)
            operations = form.history
            self.assertEqual(i + 1, len(operations))
            self.assertEqual(form.form_id, operations[i].form_id)
            self.assertEqual('user2', operations[i].user_id)

            transactions = CaseTransaction.objects.get_transactions(case_id)
            self.assertEqual(1, len(transactions))
            self.assertFalse(transactions[0].revoked)

    def test_save_new_form_and_get_attachments(self):
        unsaved_form = create_form_for_test(DOMAIN, save=False)
        XFormInstance.objects.save_new_form(unsaved_form)
        self.assertTrue(unsaved_form.is_saved())
        self.assert_form_xml_attachment(unsaved_form)

    def test_save_new_form_db_error(self):
        form = create_form_for_test(DOMAIN)
        dup_form = create_form_for_test(DOMAIN, save=False)
        dup_form.form_id = form.form_id

        # use transaction to prevent rolling back the test's transaction
        with self.assertRaises(Exception), transaction.atomic(dup_form.db):
            XFormInstance.objects.save_new_form(dup_form)

        # save should succeed with unique form id
        dup_form.form_id = uuid.uuid4().hex
        XFormInstance.objects.save_new_form(dup_form)
        self.assert_form_xml_attachment(dup_form)

    def test_save_form_deprecated(self):
        existing_form, new_form = _simulate_form_edit()

        XFormInstance.objects.update_form(existing_form, publish_changes=False)
        XFormInstance.objects.save_new_form(new_form)

        self._validate_deprecation(existing_form, new_form)

    def test_save_processed_models_deprecated(self):
        # This doesn't seem like a XFormInstanceManager test
        # Maybe should be moved to FormProcessor* tests
        existing_form, new_form = _simulate_form_edit()

        FormProcessorSQL.save_processed_models(ProcessedForms(new_form, existing_form))

        self._validate_deprecation(existing_form, new_form)

    def test_update_form_problem_and_state(self):
        form = create_form_for_test(DOMAIN)
        self.assertEqual(XFormInstance.NORMAL, form.state)

        original_domain = form.domain
        problem = 'Houston, we have a problem'
        form.state = XFormInstance.ERROR
        form.problem = problem
        form.domain = 'new domain'  # shouldn't get saved
        XFormInstance.objects.update_form_problem_and_state(form)

        saved_form = XFormInstance.objects.get_form(form.form_id)
        self.assertEqual(XFormInstance.ERROR, saved_form.state)
        self.assertEqual(problem, saved_form.problem)
        self.assertEqual(original_domain, saved_form.domain)

    def test_update_form(self):
        form = create_form_for_test(DOMAIN)
        form.user_id = 'user2'
        operation_date = datetime.utcnow()
        form.track_create(XFormOperation(
            user_id='user2',
            date=operation_date,
            operation=XFormOperation.EDIT
        ))
        XFormInstance.objects.update_form(form)

        saved_form = XFormInstance.objects.get_form(form.form_id)
        self.assertEqual('user2', saved_form.user_id)
        self.assertEqual(1, len(saved_form.history))
        self.assertEqual(operation_date, saved_form.history[0].date)

    def test_soft_delete(self):
        meta = TestFormMetadata(domain=DOMAIN)
        get_simple_wrapped_form('f1', metadata=meta)
        f2 = get_simple_wrapped_form('f2', metadata=meta)
        f2.archive()
        get_simple_wrapped_form('f3', metadata=meta)
        manager = XFormInstance.objects

        # delete
        num = manager.soft_delete_forms(DOMAIN, ['f1', 'f2'], deletion_id='123')
        self.assertEqual(num, 2)

        for form_id in ['f1', 'f2']:
            form = manager.get_form(form_id)
            self.assertTrue(form.is_deleted)
            self.assertEqual(form.deletion_id, '123')

        form = manager.get_form('f3')
        self.assertFalse(form.is_deleted)

    def test_hard_delete_forms(self):
        forms = [create_form_for_test(DOMAIN) for i in range(3)]
        form_ids = [form.form_id for form in forms]
        other_form = create_form_for_test('other_domain')
        self.addCleanup(lambda: XFormInstance.objects.hard_delete_forms('other_domain', [other_form.form_id]))
        forms = XFormInstance.objects.get_forms(form_ids)
        self.assertEqual(3, len(forms))

        deleted = XFormInstance.objects.hard_delete_forms(DOMAIN, form_ids[1:] + [other_form.form_id])
        self.assertEqual(2, deleted)
        forms = XFormInstance.objects.get_forms(form_ids)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_ids[0], forms[0].form_id)

    def assert_form_xml_attachment(self, form):
        attachments = XFormInstance.objects.get_attachments(form.form_id)
        self.assertEqual([a.name for a in attachments], ["form.xml"])

    def _validate_deprecation(self, existing_form, new_form):
        saved_new_form = XFormInstance.objects.get_form(new_form.form_id)
        deprecated_form = XFormInstance.objects.get_form(existing_form.form_id)
        self.assertEqual(deprecated_form.form_id, saved_new_form.deprecated_form_id)
        self.assertTrue(deprecated_form.is_deprecated)
        self.assertNotEqual(saved_new_form.form_id, deprecated_form.form_id)
        self.assertEqual(saved_new_form.form_id, deprecated_form.orig_id)

    def _check_simple_form(self, form):
        self.assertIsInstance(form, XFormInstance)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
        return form


class TestHardDeleteFormsBeforeCutoff(TestCase):

    def test_form_is_hard_deleted_if_deleted_on_is_before_cutoff(self):
        form = create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        XFormInstance.objects.hard_delete_forms_before_cutoff(self.cutoff, dry_run=False)

        with self.assertRaises(XFormNotFound):
            XFormInstance.objects.get_form(form.form_id)

    def test_form_is_not_hard_deleted_if_deleted_on_is_cutoff(self):
        form = create_form_for_test(self.domain, deleted_on=self.cutoff)

        XFormInstance.objects.hard_delete_forms_before_cutoff(self.cutoff, dry_run=False)

        fetched_form = XFormInstance.objects.get_form(form.form_id)
        self.assertIsNotNone(fetched_form)

    def test_form_is_not_hard_deleted_if_deleted_on_is_after_cutoff(self):
        form = create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 1, 12, 31))

        XFormInstance.objects.hard_delete_forms_before_cutoff(self.cutoff, dry_run=False)

        fetched_form = XFormInstance.objects.get_form(form.form_id)
        self.assertIsNotNone(fetched_form)

    def test_form_is_not_hard_deleted_if_deleted_on_is_null(self):
        form = create_form_for_test(self.domain, deleted_on=None)

        XFormInstance.objects.hard_delete_forms_before_cutoff(self.cutoff, dry_run=False)

        fetched_form = XFormInstance.objects.get_form(form.form_id)
        self.assertIsNotNone(fetched_form)

    def test_returns_deleted_counts(self):
        expected_count = 5
        for _ in range(expected_count):
            create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        counts = XFormInstance.objects.hard_delete_forms_before_cutoff(self.cutoff, dry_run=False)

        self.assertEqual(counts, {'form_processor.XFormInstance': 5})

    def test_nothing_is_deleted_if_dry_run_is_true(self):
        form = create_form_for_test(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        # dry_run defaults to True
        counts = XFormInstance.objects.hard_delete_forms_before_cutoff(self.cutoff)

        # should not raise XFormNotFound
        XFormInstance.objects.get_form(form.form_id)
        # still returns accurate count
        self.assertEqual(counts, {'form_processor.XFormInstance': 1})

    def setUp(self):
        self.domain = 'test_hard_delete_forms_before_cutoff'
        self.cutoff = datetime(2020, 1, 1, 12, 30)


class TempFormCacheTests(SimpleTestCase):
    def test_no_db_hit_if_cached(self):
        cache = TempFormCache()
        form = XFormInstance(form_id="1234")
        cache.cache[form.form_id] = form
        # This should not raise an AssertionError, which means it tried to access the db
        retrieved_form = cache.get_forms([form.form_id])[0]
        self.assertEqual(retrieved_form, form)


class DeleteAttachmentsFSDBTests(TestCase):
    def setUp(self):
        super(DeleteAttachmentsFSDBTests, self).setUp()
        self.db = TemporaryFilesystemBlobDB()

    def tearDown(self):
        self.db.close()
        super(DeleteAttachmentsFSDBTests, self).tearDown()

    def test_hard_delete_forms_and_attachments(self):
        forms = [create_form_for_test(DOMAIN) for i in range(3)]
        form_ids = sorted(form.form_id for form in forms)
        forms = XFormInstance.objects.get_forms(form_ids)
        self.assertEqual(3, len(forms))

        other_form = create_form_for_test('other_domain')
        self.addCleanup(lambda: XFormInstance.objects.hard_delete_forms('other_domain', [other_form.form_id]))

        attachments = sorted(
            get_blob_db().metadb.get_for_parents(form_ids),
            key=lambda meta: meta.parent_id
        )
        self.assertEqual(3, len(attachments))

        deleted = XFormInstance.objects.hard_delete_forms(DOMAIN, form_ids[1:] + [other_form.form_id])
        self.assertEqual(2, deleted)

        forms = XFormInstance.objects.get_forms(form_ids)
        self.assertEqual(1, len(forms))
        self.assertEqual(form_ids[0], forms[0].form_id)

        for attachment in attachments[1:]:
            with self.assertRaises(BlobNotFound):
                attachment.open()

        with attachments[0].open() as content:
            self.assertIsNotNone(content.read())
        other_form = XFormInstance.objects.get_form(other_form.form_id)
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


@sharded
class XFormOperationManagerTest(TestCase):

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
            FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super().tearDown()

    def test_get_form_operations(self):
        form = create_form_for_test(DOMAIN)

        operations = XFormOperation.objects.get_form_operations('missing_form')
        self.assertEqual([], operations)

        operations = XFormOperation.objects.get_form_operations(form.form_id)
        self.assertEqual([], operations)

        # don't call form.archive to avoid sending the signals
        archive_form(form, user_id='user1')
        unarchive_form(form, user_id='user2')

        operations = XFormOperation.objects.get_form_operations(form.form_id)
        self.assertEqual(2, len(operations))
        self.assertEqual('user1', operations[0].user_id)
        self.assertEqual(XFormOperation.ARCHIVE, operations[0].operation)
        self.assertIsNotNone(operations[0].date)
        self.assertEqual('user2', operations[1].user_id)
        self.assertEqual(XFormOperation.UNARCHIVE, operations[1].operation)
        self.assertIsNotNone(operations[1].date)
        self.assertGreater(operations[1].date, operations[0].date)


def archive_form(form, user_id):
    XFormInstance.objects.set_archived_state(form, True, user_id)


def unarchive_form(form, user_id):
    XFormInstance.objects.set_archived_state(form, False, user_id)


def _simulate_form_edit():
    existing_form = create_form_for_test(DOMAIN, save=False)
    XFormInstance.objects.save_new_form(existing_form)
    existing_form = XFormInstance.objects.get_form(existing_form.form_id)

    new_form = create_form_for_test(DOMAIN, save=False)
    new_form.form_id = existing_form.form_id

    existing_form, new_form = apply_deprecation(existing_form, new_form)
    assert existing_form.form_id != new_form.form_id
    return existing_form, new_form
