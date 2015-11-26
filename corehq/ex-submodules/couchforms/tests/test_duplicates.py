import os
from django.test import TestCase

from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends, post_xform, UuidAssertMixin
from corehq.util.test_utils import TestFileMixin


class DuplicateFormTest(TestCase, TestFileMixin, UuidAssertMixin):
    ID = 'f7f0c79e-8b79-11df-b7de-005056c00009'
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()

    @run_with_all_backends
    def test_basic_duplicate(self):
        xml_data = self.get_xml('duplicate')
        xform = post_xform(xml_data)
        self.assertUuidEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("test-domain", xform.domain)

        xform = post_xform(xml_data, domain='test-domain')
        self.assertUuidNotEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_duplicate)
        self.assertTrue(str(self.ID) in xform.problem)

    @run_with_all_backends
    def test_wrong_doc_type(self):
        domain = 'test-domain'
        instance = self.get_xml('duplicate')

        # Post an xform with an alternate doc_type
        xform1 = post_xform(instance, domain=domain)

        # Change the doc_type of the form by archiving it
        xform1.archive()
        xform1 = FormAccessors().get_form(xform1.form_id)
        self.assertTrue(xform1.is_archived)

        # Post an xform with that has different doc_type but same id
        _, xform2, _ = submit_form_locally(
            instance,
            domain=domain,
        )

        self.assertNotEqual(xform1.form_id, xform2.form_id)

    @run_with_all_backends
    def test_wrong_domain(self):
        domain = 'test-domain'
        instance = self.get_xml('duplicate')

        _, xform1, _ = submit_form_locally(
            instance,
            domain='wrong-domain',
        )
        _, xform2, _ = submit_form_locally(
            instance,
            domain=domain,
        )
        self.assertNotEqual(xform1.form_id, xform2.form_id)
