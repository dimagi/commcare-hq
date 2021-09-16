from django.conf import settings
from django.test import TestCase

from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_form_for_test,
    sharded,
)

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

    def _check_simple_form(self, form):
        self.assertIsInstance(form, XFormInstance)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
        return form
