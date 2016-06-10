from mock import MagicMock
import os
import uuid

from django.core.management import call_command
from django.test import TestCase
from elasticsearch import ConnectionError
from testil import tempdir

from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests import TestXmlMixin
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.cleanup.management.commands.fix_forms_with_missing_xmlns import (
    generate_random_xmlns,
    set_xmlns_on_form,
)
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from couchforms.models import XFormInstance
from pillowtop.es_utils import completely_initialize_pillow_index

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
        dup_2_id = self._submit_form(form_with_multi_dups_id)._id
        dup_3_id = self._submit_form(form_with_multi_dups_id)._id
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
            self.assertIsNone(dup.problem)

            form_with_multi_dups = XFormInstance.get(form_with_multi_dups_id)
            self.assertEqual(form_with_multi_dups.doc_type, "XFormInstance")

            another_form = XFormInstance.get(another_form_id)
            self.assertEqual(another_form.doc_type, "XFormInstance")
