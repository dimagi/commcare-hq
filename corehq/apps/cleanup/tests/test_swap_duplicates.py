import os
import uuid

from django.core.management import call_command
from django.test import TestCase
from testil import tempdir

from corehq.apps.app_manager.tests import TestXmlMixin
from corehq.apps.receiverwrapper import submit_form_locally
from couchforms.models import XFormInstance

DOMAIN = "test"


class TestFixFormsWithMissingXmlns(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def _submit_form(self, id_=None):
        xform_source = self.get_xml('xform_template').format(xmlns="foo", name="bar", id=id_ or uuid.uuid4().hex)
        _, xform, __ = submit_form_locally(xform_source, DOMAIN)
        return xform

    def test_swap(self):
        # Test a form with a single dup
        form_id = self._submit_form()._id
        dup_id = self._submit_form(form_id)._id
        # Test a form with multiple dups
        form_with_multi_dups_id = self._submit_form()._id
        self._submit_form(form_with_multi_dups_id)
        self._submit_form(form_with_multi_dups_id)
        # Test a form with no dups
        another_form_id = self._submit_form()._id

        with tempdir() as tmp:
            ids_file_path = os.path.join(tmp, 'ids')

            with open(ids_file_path, "w") as ids_file:
                for id_ in (form_id, form_with_multi_dups_id, another_form_id):
                    ids_file.write("{} {}\n".format(DOMAIN, id_))

            call_command('swap_duplicate_xforms', ids_file_path, '/dev/null', no_input=True)

            form = XFormInstance.get(form_id)
            self.assertEqual(form.doc_type, "XFormDuplicate")
            self.assertIsNotNone(form.problem)

            dup = XFormInstance.get(dup_id)
            self.assertEqual(dup.doc_type, "XFormInstance")
            self.assertTrue(dup.problem.startswith("This document was an xform duplicate that"))

            form_with_multi_dups = XFormInstance.get(form_with_multi_dups_id)
            self.assertEqual(form_with_multi_dups.doc_type, "XFormInstance")

            another_form = XFormInstance.get(another_form_id)
            self.assertEqual(another_form.doc_type, "XFormInstance")
