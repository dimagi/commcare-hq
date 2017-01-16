from mock import MagicMock, patch
import os
import uuid

from django.core.management import call_command
from django.test import TestCase
from elasticsearch import ConnectionError
from testil import tempdir

from casexml.apps.case.tests.util import delete_all_xforms
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestXmlMixin, delete_all_apps
from corehq.apps.app_manager.util import get_correct_app_class
from corehq.apps.cleanup.management.commands.fix_forms_and_apps_with_missing_xmlns import (
    generate_random_xmlns,
    set_xmlns_on_form,
)
from corehq.apps.cleanup.tasks import fix_xforms_with_missing_xmlns
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.pillows.xform import transform_xform_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from couchforms.models import XFormInstance
from pillowtop.es_utils import initialize_index_and_mapping

DOMAIN = "test"


class TestFixFormsWithMissingXmlns(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        super(TestFixFormsWithMissingXmlns, cls).setUpClass()
        cls.es = get_es_new()
        with trap_extra_setup(ConnectionError, msg="cannot connect to elasicsearch"):
            initialize_index_and_mapping(cls.es, XFORM_INDEX_INFO)

    def setUp(self):
        super(TestFixFormsWithMissingXmlns, self).setUp()
        delete_all_apps()
        delete_all_xforms()

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(XFORM_INDEX_INFO.index)
        super(TestFixFormsWithMissingXmlns, cls).tearDownClass()

    def _submit_form(self, xmlns, form_name, app_id, build_id):
        xform_source = self.get_xml('xform_template').format(xmlns=xmlns, name=form_name, id=uuid.uuid4().hex)
        _, xform, __ = submit_form_locally(xform_source, DOMAIN, app_id=app_id, build_id=build_id)
        send_to_elasticsearch('forms', transform_xform_for_elasticsearch(xform.to_json()))
        return xform

    def _refresh_pillow(self):
        self.es.indices.refresh(XFORM_INDEX_INFO.index)

    @patch("corehq.apps.app_manager.models.validate_xform", return_value=None)
    def build_normal_app(self, mock):
        xmlns = generate_random_xmlns()
        form_name = "Untitled Form"

        app = Application.new_app(DOMAIN, 'Normal App')
        module = app.add_module(Module.new_module('New Module', lang='en'))
        form_source = self.get_xml('form_template').format(xmlns=xmlns, name=form_name)
        form = module.new_form(form_name, "en", form_source)
        app.save()
        build = app.make_build()
        build.save()

        xform = self._submit_form(xmlns, form_name, app._id, build._id)
        return form, xform

    @patch("corehq.apps.app_manager.models.validate_xform", side_effect=None)
    def build_app_with_bad_form(self, mock):
        """
        Generates an app with one normal form, and one form with "undefined" xmlns
        Generates submissions against both forms.
        """
        xmlns = generate_random_xmlns()
        good_form_name = "Untitled Form"
        bad_form_name = "Bad Form"

        app = Application.new_app(DOMAIN, 'Normal App')
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

    @patch("corehq.apps.app_manager.models.validate_xform", side_effect=None)
    def build_app_with_recently_fixed_form(self, mock):
        """
        Generates an app with a form that:
        - had an "undefined" xmlns
        - had forms submitted with the bad xmlns
        - had xmlns changed to something real
        - had forms submitted with real xmlns
        """
        form_name = "Untitled Form"

        app = Application.new_app(DOMAIN, 'Normal App')
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

        app = Application.new_app(DOMAIN, 'Normal App')
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

        with tempdir() as tmp:
            log_file = os.path.join(tmp, 'log.txt')

            call_command('fix_forms_and_apps_with_missing_xmlns', '/dev/null', log_file)

            with open(log_file) as log_file:
                log = log_file.read()
                self.assertTrue(form.unique_id not in log)
                self.assertTrue(xform._id not in log)

    def test_app_with_bad_form(self):
        good_form, bad_form, good_xform, bad_xforms = self.build_app_with_bad_form()
        self._refresh_pillow()

        with tempdir() as tmp:
            log_file = os.path.join(tmp, 'log.txt')

            call_command('fix_forms_and_apps_with_missing_xmlns', '/dev/null', log_file)

            with open(log_file) as log_file:
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

        with tempdir() as tmp:
            log_file = os.path.join(tmp, 'log.txt')

            call_command('fix_forms_and_apps_with_missing_xmlns', '/dev/null', log_file)

            with open(log_file) as log_file:
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

    def test_fix_xforms_with_missing_xmlns_task(self):
        """Tests the ability to find anomalies that violate our asssumptions
        about all applications and builds being fixes
        """

        good_form, bad_form, good_xform, bad_xforms = self.build_app_with_bad_form()
        self._refresh_pillow()

        with tempdir() as tmp:
            with patch('corehq.apps.cleanup.tasks.UNDEFINED_XMLNS_LOG_DIR', tmp):
                with patch('corehq.apps.cleanup.tasks.mail_admins_async') as mocked_mail:
                    stats, log_file_path = fix_xforms_with_missing_xmlns()
                    self.assertTrue(mocked_mail.delay.called)

            self.assertTrue(
                (DOMAIN, bad_xforms[0].build_id) in stats['builds_with_undefined_xmlns']
            )
            self.assertEqual(stats['not_fixed_undefined_xmlns'][DOMAIN], len(bad_xforms))

    def test_fix_xforms_with_missing_xmlns_task_fixed(self):
        """Tests the ability to fix xforms with the periodic cron task
        """

        good_form, bad_form, good_xform, bad_xforms = self.build_app_with_bad_form()
        # Fix bad builds
        for bad_xform in bad_xforms:
            app = Application.get(bad_xform.build_id)
            for form in app.get_forms():
                if form.xmlns == 'undefined':
                    form.xmlns = 'my-fixed-xmlns'
            app.save()

        self._refresh_pillow()

        with tempdir() as tmp:
            with patch('corehq.apps.cleanup.tasks.UNDEFINED_XMLNS_LOG_DIR', tmp):
                with patch('corehq.apps.cleanup.tasks.mail_admins_async') as mocked_mail:
                    stats, log_file_path = fix_xforms_with_missing_xmlns()
                    self.assertTrue(mocked_mail.delay.called)

        self.assertTrue(stats['fixed'][DOMAIN], len(bad_xforms))

    def assertNoMissingXmlnss(self, delete_apps=True):
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
        try:
            for app in apps:
                for form in app.get_forms():
                    self.assertEqual(form.source.count('xmlns="undefined"'), 0)
                    self.assertNotEqual(form.xmlns, 'undefined')
        finally:
            if delete_apps:
                for app in apps:
                    app.delete()
