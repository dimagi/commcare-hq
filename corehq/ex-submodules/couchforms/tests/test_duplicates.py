import os
from django.test import TestCase

from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.interfaces.xform import XFormInterface
from corehq.form_processor.test_utils import FormProcessorTestUtils
from corehq.form_processor.generic import GenericXFormInstance
from couchforms.models import XFormInstance
from corehq.util.test_utils import TestFileMixin


class DuplicateFormTest(TestCase, TestFileMixin):
    ID = '7H46J37FGH3'
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()

    def test_basic_duplicate(self):
        xml_data = self.get_xml('duplicate')
        xform = FormProcessorInterface().post_xform(xml_data)
        self.assertEqual(self.ID, xform.id)
        self.assertEqual("XFormInstance", xform.doc_type)
        self.assertEqual("test-domain", xform.domain)

        xform = FormProcessorInterface().post_xform(xml_data, domain='test-domain')
        self.assertNotEqual(self.ID, xform.id)
        self.assertEqual("XFormDuplicate", xform.doc_type)
        self.assertTrue(self.ID in xform.problem)

    def test_wrong_doc_type(self):
        domain = 'test-domain'
        instance = self.get_xml('duplicate')

        # Post an xform with an alternate doc_type
        xform1 = FormProcessorInterface().post_xform(
            instance,
            domain=domain,
        )

        # Change the doc_type of the form by archiving it
        XFormInterface(domain).archive(xform1)
        xform1 = XFormInterface(domain).get_xform(xform1.id)
        self.assertTrue(xform1.is_archived)

        # Post an xform with that has different doc_type but same id
        _, xform2, _ = FormProcessorInterface().submit_form_locally(
            instance,
            domain=domain,
        )

        self.assertNotEqual(xform1.id, xform2.id)

    def test_wrong_domain(self):
        domain = 'test-domain'
        instance = self.get_xml('duplicate')

        _, xform1, _ = FormProcessorInterface().submit_form_locally(
            instance,
            domain='wrong-domain',
        )
        _, xform2, _ = FormProcessorInterface().submit_form_locally(
            instance,
            domain=domain,
        )
        self.assertNotEqual(xform1.id, xform2.id)
