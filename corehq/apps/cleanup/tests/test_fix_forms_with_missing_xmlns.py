import os
import uuid

from django.core.management import call_command
from django.test import TestCase
from elasticsearch import ConnectionError

from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests import TestXmlMixin
from corehq.apps.cleanup.management.commands.fix_forms_with_missing_xmlns import \
    generate_random_xmlns
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.pillows.xform import XFormPillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import completely_initialize_pillow_index

DOMAIN = "test"

class TestFixFormsWithMissingXmlns(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        cls.form_pillow = XFormPillow(online=False)
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            completely_initialize_pillow_index(cls.form_pillow)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(cls.form_pillow.es_index)

    def _submit_form(self, xmlns, form_name, app_id):
        xform_source = self.get_xml('xform_template').format(xmlns=xmlns, name=form_name, id=uuid.uuid4().hex)
        _, xform, __ = submit_form_locally(xform_source, DOMAIN, app_id=app_id)
        self.form_pillow.send_robust(self.form_pillow.change_transform(xform.to_json()))
        return xform

    def _refresh_pillow(self):
        self.form_pillow.get_es_new().indices.refresh(self.form_pillow.es_index)

    def build_normal_app(self):
        xmlns = generate_random_xmlns()
        form_name = "Untitled Form"

        app = Application.new_app(DOMAIN, 'Normal App', APP_V2)
        module = app.add_module(Module.new_module('New Module', lang='en'))
        form_source = self.get_xml('form_template').format(xmlns=xmlns, name=form_name)
        form = module.new_form(form_name, "en", form_source)
        app.save()

        xform = self._submit_form(xmlns, form_name, app._id)
        return form, xform

    def build_app_with_bad_form(self):
        """
        Generates an app with one normal form, and one form with "undefined" xmlns
        Generates submissions against both forms.
        """
        xmlns = generate_random_xmlns()
        good_form_name = "Untitled Form"
        bad_form_name = "Bad Form"

        app = Application.new_app(DOMAIN, 'Normal App', APP_V2)
        module = app.add_module(Module.new_module('New Module', lang='en'))
        good_form_source = self.get_xml('form_template').format(xmlns=xmlns, name=good_form_name)
        good_form = module.new_form(good_form_name, "en", good_form_source)
        bad_form_source = self.get_xml('form_template').format(xmlns="undefined", name=bad_form_name)
        bad_form = module.new_form(bad_form_name, "en", bad_form_source)
        app.save()

        good_xform = self._submit_form(xmlns, good_form_name, app._id)

        bad_xforms = []
        for i in range(2):
            bad_xform = self._submit_form("undefined", bad_form_name, app._id)
            bad_xforms.append(bad_xform)

        return good_form, bad_form, good_xform, bad_xforms

    def build_app_with_two_bad_forms(self):
        """
        Generates an app with two forms, both with "undefined" xmlns
        Generates submissions against both forms.
        """
        form_names = ["Bad Form 1", "Bad Form 2"]

        app = Application.new_app(DOMAIN, 'Normal App', APP_V2)
        module = app.add_module(Module.new_module('New Module', lang='en'))

        forms = []
        for form_name in form_names:
            form_source = self.get_xml('form_template').format(xmlns="undefined", name=form_name)
            forms.append(module.new_form(form_name, "en", form_source))
        app.save()

        xforms = []
        for form_name in form_names:
            xforms.append(
                self._submit_form("undefined", form_name, app._id)
            )

        return forms, xforms

    def build_app_with_recently_bad_form(self):
        """
        Generates an app with a form that:
        - had a real xmlns
        - had forms submitted with the real xmlns
        - had a xmlns changed to "undefined"
        - had forms submitted with "undefined" xmlns
        """
        form_name = "Untitled Form"

        app = Application.new_app(DOMAIN, 'Normal App', APP_V2)
        module = app.add_module(Module.new_module('New Module', lang='en'))
        form_source = self.get_xml('form_template').format(
            xmlns=uuid.uuid4().hex, name=form_name
        )
        form = module.new_form(form_name, "en", form_source)
        app.save()

        good_xform = self._submit_form(form.xmlns, form_name, app._id)

        form.source = self.get_xml('form_template').format(
            xmlns="undefined", name=form_name
        )
        app.save()

        bad_xform = self._submit_form(form.xmlns, form_name, app._id)

        return form, good_xform, bad_xform

    def test_normal_app(self):
        form, xform = self.build_normal_app()
        self._refresh_pillow()

        call_command('fix_forms_with_missing_xmlns', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            self.assertTrue(form.unique_id not in log)
            self.assertTrue(xform._id not in log)

    def test_app_with_bad_form(self):
        good_form, bad_form, good_xform, bad_xforms = self.build_app_with_bad_form()
        self._refresh_pillow()

        call_command('fix_forms_with_missing_xmlns', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            self.assertTrue(good_form.unique_id not in log)
            self.assertTrue(bad_form.unique_id in log)
            self.assertTrue(good_xform._id not in log)
            for xform in bad_xforms:
                self.assertTrue(xform._id in log)

    def test_app_with_two_bad_forms(self):
        forms, xforms = self.build_app_with_two_bad_forms()
        self._refresh_pillow()
        call_command('fix_forms_with_missing_xmlns', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            for id_ in [f.unique_id for f in forms] + [f._id for f in xforms]:
                self.assertTrue(id_ not in log)

    def test_app_with_recently_bad_form(self):
        """
        Confirm that a form which
        - had a real xmlns
        - had forms submitted with the real xmlns
        - had a xmlns changed to "undefined"
        - had forms submitted with "undefined" xmlns
        does not get a new random xmlns
        """
        form, good_xform, bad_xform = self.build_app_with_recently_bad_form()
        self._refresh_pillow()
        call_command('fix_forms_with_missing_xmlns', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            self.assertTrue(form.unique_id not in log)
            self.assertTrue(good_xform._id not in log)
            self.assertTrue(bad_xform._id not in log)
