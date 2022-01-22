import uuid

from django.conf import settings
from django.db import transaction
from django.test import TestCase

from corehq.sql_db.util import get_db_alias_for_partitioned_doc

from ..exceptions import AttachmentNotFound, XFormNotFound
from ..models import XFormInstance
from ..tests.utils import FormProcessorTestUtils, create_form_for_test, sharded
from ..utils import get_simple_form_xml

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

    def assert_form_xml_attachment(self, form):
        attachments = XFormInstance.objects.get_attachments(form.form_id)
        self.assertEqual([a.name for a in attachments], ["form.xml"])

    def _check_simple_form(self, form):
        self.assertIsInstance(form, XFormInstance)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
        return form
