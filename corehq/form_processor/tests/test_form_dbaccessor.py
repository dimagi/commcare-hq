import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.models import XFormInstanceSQL
from crispy_forms.tests.utils import override_settings

DOMAIN = 'test-form-accessor'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class FormAccessorTests(TestCase):

    def test_get_form_by_id(self):
        case_id = uuid.uuid4().hex
        form_id = submit_case_blocks(
            CaseBlock(create=True, case_id=case_id).as_string(),
            domain=DOMAIN,
            user_id='user1',
        )
        form = FormAccessorSQL().get_form(form_id)
        self.assertIsInstance(form, XFormInstanceSQL)
        self.assertIsNotNone(form)
        self.assertEqual(DOMAIN, form.domain)
        self.assertEqual('user1', form.user_id)
