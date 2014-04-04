import os
from django.test import TestCase
from couchforms.models import XFormInstance
from couchforms.util import post_xform_to_couch, create_and_lock_xform


class DuplicateFormTest(TestCase):

    def tearDown(self):
        try:
            XFormInstance.get_db().delete_doc("7H46J37FGH3")
        except:
            pass

    def _get_file(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "duplicate.xml")
        with open(file_path, "rb") as f:
            return f.read()

    def test_basic_duplicate(self):
        xml_data = self._get_file()
        doc = post_xform_to_couch(xml_data)
        self.assertEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual("XFormInstance", doc.doc_type)
        doc.domain = 'test-domain'
        doc.save()

        doc = post_xform_to_couch(xml_data, domain='test-domain')
        self.assertNotEqual("7H46J37FGH3", doc.get_id)
        self.assertEqual("XFormDuplicate", doc.doc_type)
        self.assertTrue("7H46J37FGH3" in doc.problem)

        dupe_id = doc.get_id

        XFormInstance.get_db().delete_doc("7H46J37FGH3")
        XFormInstance.get_db().delete_doc(dupe_id)

    def test_wrong_doc_type(self):
        domain = 'test-domain'
        id = '7H46J37FGH3'
        XFormInstance.get_db().save_doc({
            '_id': id,
            'doc_type': 'Foo',
            'domain': domain,
        })

        doc = post_xform_to_couch(instance=self._get_file(), domain=domain)
        self.assertNotEqual(doc.get_id, id)

    def test_wrong_domain(self):
        domain = 'test-domain'
        id = '7H46J37FGH3'
        XFormInstance.get_db().save_doc({
            '_id': id,
            'doc_type': 'XFormInstance',
            'domain': 'wrong-domain',
        })

        doc = post_xform_to_couch(instance=self._get_file(), domain=domain)
        self.assertNotEqual(doc.get_id, id)
