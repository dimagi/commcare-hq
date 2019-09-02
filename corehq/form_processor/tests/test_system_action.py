from uuid import uuid4

from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally

from ..exceptions import XFormNotFound
from ..interfaces.dbaccessors import FormAccessors
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
            FormAccessors(domain).get_form(form_id)
