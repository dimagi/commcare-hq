import os
from django.test import TestCase
from couchforms.models import XFormInstance

from corehq.form_processor.interfaces import FormProcessorInterface
from corehq.form_processor.generic import GenericXFormInstance


class DuplicateFormTest(TestCase):
    ID = '7H46J37FGH3'

    def tearDown(self):
        XFormInstance.get_db().flush()

    def _get_file(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "duplicate.xml")
        with open(file_path, "rb") as f:
            return f.read()

    def test_basic_duplicate(self):
        xml_data = self._get_file()
        xform = FormProcessorInterface.post_xform(xml_data)
        self.assertEqual(self.ID, xform.id)
        self.assertEqual("XFormInstance", xform.doc_type)
        self.assertEqual("test-domain", xform.domain)

        xform = FormProcessorInterface.post_xform(xml_data, domain='test-domain')
        self.assertNotEqual(self.ID, xform.id)
        self.assertEqual("XFormDuplicate", xform.doc_type)
        self.assertTrue(self.ID in xform.problem)

    def test_wrong_doc_type(self):
        domain = 'test-domain'
        generic_xform = GenericXFormInstance(
            doc_type='Foo',
            domain=domain,
        )
        xform = FormProcessorInterface.create_from_generic(generic_xform)

        instance = self._get_file()
        instance = instance.replace(self.ID, xform.id)
        xform = FormProcessorInterface.post_xform(instance, domain=domain)
        self.assertNotEqual(xform.id, self.ID)

    def test_wrong_domain(self):
        domain = 'test-domain'
        generic_xform = GenericXFormInstance(
            doc_type='XFormInstance',
            domain='wrong-domain',
        )
        xform = FormProcessorInterface.create_from_generic(generic_xform)

        instance = self._get_file()
        instance = instance.replace(self.ID, xform.id)
        xform = FormProcessorInterface.post_xform(instance, domain=domain)
        self.assertNotEqual(xform.id, self.ID)
