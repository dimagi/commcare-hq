from mock import MagicMock
import os
import uuid

from django.core.management import call_command
from django.test import TestCase
from elasticsearch import ConnectionError

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

    @classmethod
    def setUpClass(cls):
        cls.form_pillow = XFormPillow(online=False)
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            completely_initialize_pillow_index(cls.form_pillow)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(cls.form_pillow.es_index)

    def _submit_form(self, xmlns, form_name, app_id, build_id):
        xform_source = self.get_xml('xform_template').format(xmlns=xmlns, name=form_name, id=uuid.uuid4().hex)
        _, xform, __ = submit_form_locally(xform_source, DOMAIN, app_id=app_id, build_id=build_id)
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
        build = app.make_build()
        build.save()

        xform = self._submit_form(xmlns, form_name, app._id, build._id)
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
        build = app.make_build()
        build.save()

        good_xform = self._submit_form(xmlns, good_form_name, app._id, build._id)

        bad_xforms = []
        for i in range(2):
            bad_xform = self._submit_form("undefined", bad_form_name, app._id, build._id)
            bad_xforms.append(bad_xform)

        return good_form, bad_form, good_xform, bad_xforms

    def build_app_with_recently_fixed_form(self):
        """
        Generates an app with a form that:
        - had an "undefined" xmlns
        - had forms submitted with the bad xmlns
        - had xmlns changed to something real
        - had forms submitted with real xmlns
        """
        form_name = "Untitled Form"

        app = Application.new_app(DOMAIN, 'Normal App', APP_V2)
        module = app.add_module(Module.new_module('New Module', lang='en'))
        form_source = self.get_xml('form_template').format(
            xmlns="undefined", name=form_name
        )
        form = module.new_form(form_name, "en", form_source)
        app.save()
        bad_build = app.make_build()
        bad_build.save()

        bad_xform = self._submit_form(form.xmlns, form_name, app._id, bad_build._id)

        xmlns = generate_random_xmlns()
        form = app.get_form(form.unique_id)
        form.source = self.get_xml('form_template').format(
            xmlns=xmlns, name=form_name
        )
        form.xmlns = xmlns
        app.save()

        good_build = app.make_build()
        good_build.save()
        good_xform = self._submit_form(form.xmlns, form_name, app._id, good_build._id)

        return form, good_build, bad_build, good_xform, bad_xform

    def build_app_with_bad_source_and_good_json(self):
        """
        Generates an app with a form that has a converted json xmlns but an unconverted source
        """
        form_name = "Untitled Form"

        app = Application.new_app(DOMAIN, 'Normal App', APP_V2)
        module = app.add_module(Module.new_module('New Module', lang='en'))
        form_source = self.get_xml('form_template').format(
            xmlns="undefined", name=form_name
        )
        form = module.new_form(form_name, "en", form_source)
        form.xmlns = 'not-at-all-undefined'
        app.save()

        return form, app

    def test_normal_app(self):
        form, xform = self.build_normal_app()
        self._refresh_pillow()

        call_command('fix_forms_with_missing_xmlns', '/dev/null', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            self.assertTrue(form.unique_id not in log)
            self.assertTrue(xform._id not in log)

    def test_app_with_bad_form(self):
        good_form, bad_form, good_xform, bad_xforms = self.build_app_with_bad_form()
        self._refresh_pillow()

        call_command('fix_forms_with_missing_xmlns', '/dev/null', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            self.assertTrue(good_form.unique_id not in log)
            self.assertTrue(bad_form.unique_id in log)
            self.assertTrue(good_xform._id not in log)
            for xform in bad_xforms:
                self.assertTrue(xform._id in log)
        self.assertNoMissingXmlnss()

    def test_app_with_recently_fixed_form(self):
        form, good_build, bad_build, good_xform, bad_xform = self.build_app_with_recently_fixed_form()
        self._refresh_pillow()

        call_command('fix_forms_with_missing_xmlns', '/dev/null', 'log.txt')

        with open("log.txt") as log_file:
            log = log_file.read()
            self.assertTrue(good_build._id not in log)
            self.assertTrue(bad_build._id in log)
            self.assertTrue(good_xform._id not in log)
            self.assertTrue(bad_xform._id in log)
        self.assertNoMissingXmlnss()

    def test_app_with_good_form_json_and_bad_source(self):
        form, app = self.build_app_with_bad_source_and_good_json()
        set_xmlns_on_form(
            form.unique_id,
            'not-at-all-undefined',
            app,
            MagicMock(),
            False
        )
        self.assertNoMissingXmlnss()

    def assertNoMissingXmlnss(self):
        submissions = XFormInstance.get_db().view(
            'couchforms/by_xmlns',
            key="undefined",
            include_docs=False,
            reduce=False,
        ).all()
        self.assertEqual(submissions, [])

        saved_apps = Application.get_db().view(
            'app_manager/saved_app',
            include_docs=True,
        )
        apps = [get_correct_app_class(row['doc']).wrap(row['doc']) for row in saved_apps]
        for app in apps:
            for form in app.get_forms():
                self.assertEqual(form.source.count('xmlns="undefined"'), 0)
                self.assertNotEqual(form.xmlns, 'undefined')
