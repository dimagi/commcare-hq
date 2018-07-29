from __future__ import absolute_import
from __future__ import unicode_literals
import os
from django.conf import settings
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.util.test_utils import TestFileMixin


class DuplicateFormTest(TestCase, TestFileMixin):
    ID = '7H46J37FGH3'
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()

    def test_basic_duplicate(self):
        xml_data = self.get_xml('duplicate')
        xform = submit_form_locally(xml_data, 'test-domain').xform
        self.assertEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_normal)
        self.assertEqual("test-domain", xform.domain)

        xform = submit_form_locally(xml_data, 'test-domain').xform
        self.assertNotEqual(self.ID, xform.form_id)
        self.assertTrue(xform.is_duplicate)
        self.assertTrue(self.ID in xform.problem)
        if getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False):
            self.assertEqual(self.ID, xform.orig_id)

    def test_wrong_doc_type(self):
        domain = 'test-domain'
        instance = self.get_xml('duplicate')

        # Post an xform with an alternate doc_type
        xform1 = submit_form_locally(instance, domain=domain).xform

        # Change the doc_type of the form by archiving it
        xform1.archive()
        xform1 = FormAccessors().get_form(xform1.form_id)
        self.assertTrue(xform1.is_archived)

        # Post an xform with that has different doc_type but same id
        result = submit_form_locally(
            instance,
            domain=domain,
        )

        self.assertNotEqual(xform1.form_id, result.xform.form_id)

    def test_wrong_domain(self):
        domain = 'test-domain'
        instance = self.get_xml('duplicate')

        result1 = submit_form_locally(
            instance,
            domain='wrong-domain',
        )
        result2 = submit_form_locally(
            instance,
            domain=domain,
        )
        self.assertNotEqual(result1.xform.form_id, result2.xform.form_id)


@use_sql_backend
class DuplicateFormTestSQL(DuplicateFormTest):
    pass
