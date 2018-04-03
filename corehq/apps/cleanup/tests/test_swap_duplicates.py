from __future__ import absolute_import
from __future__ import unicode_literals
import os
import uuid

from django.core.management import call_command
from django.test import TestCase
from testil import tempdir

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.cleanup.management.commands.swap_duplicate_xforms import \
    FIXED_FORM_PROBLEM_TEMPLATE, BAD_FORM_PROBLEM_TEMPLATE
from corehq.apps.receiverwrapper.util import submit_form_locally
from couchforms.models import XFormInstance

DOMAIN = "test"


class TestFixFormsWithMissingXmlns(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    def _submit_form(self, id_=None):
        xform_source = self.get_xml('xform_template').format(xmlns="foo", name="bar", id=id_ or uuid.uuid4().hex)
        result = submit_form_locally(xform_source, DOMAIN)
        return result.xform

    def test_simple_swap(self):
        # Test a form with a single dup
        bad_form_id = self._submit_form()._id
        good_dup_id = self._submit_form(bad_form_id)._id

        with tempdir() as tmp:
            ids_file_path = os.path.join(tmp, 'ids')

            with open(ids_file_path, "w") as ids_file:
                ids_file.write("{} {}\n".format(DOMAIN, bad_form_id))

            call_command('swap_duplicate_xforms', ids_file_path, '/dev/null', no_input=True)
            # Throw in a second call to the script to test idempotence as well
            call_command('swap_duplicate_xforms', ids_file_path, '/dev/null', no_input=True)

            bad_form = XFormInstance.get(bad_form_id)
            self.assertEqual(bad_form.doc_type, "XFormDuplicate")
            self.assertRegexpMatches(
                bad_form.problem, BAD_FORM_PROBLEM_TEMPLATE.format(good_dup_id, "")
            )

            good_dup_form = XFormInstance.get(good_dup_id)
            self.assertEqual(good_dup_form.doc_type, "XFormInstance")
            self.assertRegexpMatches(
                good_dup_form.problem, FIXED_FORM_PROBLEM_TEMPLATE.format(
                    id_=bad_form_id, datetime_=""
                )
            )

    def test_non_swaps(self):
        # Test a form with multiple dups
        form_with_multi_dups_id = self._submit_form()._id
        self._submit_form(form_with_multi_dups_id)
        self._submit_form(form_with_multi_dups_id)
        # Test a form with no dups
        another_form_id = self._submit_form()._id

        with tempdir() as tmp:
            ids_file_path = os.path.join(tmp, 'ids')

            with open(ids_file_path, "w") as ids_file:
                for id_ in (form_with_multi_dups_id, another_form_id):
                    ids_file.write("{} {}\n".format(DOMAIN, id_))

            call_command('swap_duplicate_xforms', ids_file_path, '/dev/null', no_input=True)

            form_with_multi_dups = XFormInstance.get(form_with_multi_dups_id)
            self.assertEqual(form_with_multi_dups.doc_type, "XFormInstance")

            another_form = XFormInstance.get(another_form_id)
            self.assertEqual(another_form.doc_type, "XFormInstance")
