import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import XFormInstanceSQL
from crispy_forms.tests.utils import override_settings

DOMAIN = 'test-form-accessor'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class FormAccessorTests(TestCase):

    def test_get_form_by_id(self):
        form_id = self._submit_simple_form()
        with self.assertNumQueries(1):
            form = FormAccessorSQL.get_form(form_id)
        self._check_simple_form(form)

    def test_get_form_by_id_missing(self):
        with self.assertRaises(XFormNotFound):
            FormAccessorSQL.get_form('missing_form')

    def test_get_with_attachments(self):
        form_id = self._submit_simple_form()
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

    def _submit_simple_form(self):
        case_id = uuid.uuid4().hex
        return submit_case_blocks(
            CaseBlock(create=True, case_id=case_id).as_string(),
            domain=DOMAIN,
            user_id='user1',
        )

    def _check_simple_form(self, form):
        self.assertIsInstance(form, XFormInstanceSQL)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
        return form
