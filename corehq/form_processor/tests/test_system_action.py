from uuid import uuid4

import pytest
from django.test import TestCase

from testil import eq

from corehq.apps.receiverwrapper.util import submit_form_locally

from ..exceptions import XFormNotFound
from ..models.forms import ARCHIVE_FORM
from ..interfaces.processor import HARD_DELETE_CASE_AND_FORMS
from ..models import XFormInstance
from ..system_action import SYSTEM_ACTION_XMLNS, UnauthorizedSystemAction
from ..utils import TestFormMetadata, get_simple_form_xml


class TestSystemActions(TestCase):

    def test_unauthorized_system_action(self):
        domain = uuid4().hex
        form_id = uuid4().hex
        meta = TestFormMetadata(domain=domain, xmlns=SYSTEM_ACTION_XMLNS)
        xml = get_simple_form_xml(form_id, metadata=meta)
        with self.assertRaises(UnauthorizedSystemAction):
            submit_form_locally(xml, domain)
        with self.assertRaises(XFormNotFound):
            XFormInstance.objects.get_form(form_id, domain)


@pytest.mark.parametrize("actual, expected", [
    (ARCHIVE_FORM, "archive_form"),
    (HARD_DELETE_CASE_AND_FORMS, "hard_delete_case_and_forms"),
])
def test_system_action_constants(actual, expected):
    eq(actual, expected,
        f"Changing the value of this constant will break all "
        f"'{expected}' system action forms in existence.")
