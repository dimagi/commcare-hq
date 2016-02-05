import json
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.tests.util import add_build, patch_default_builds
from corehq.apps.app_manager.util import add_odk_profile_after_build
from dimagi.utils.decorators.memoized import memoized
import os
import codecs

from django.test import TestCase, SimpleTestCase
from corehq.apps.app_manager.models import Application, DetailColumn, import_app, APP_V1, ApplicationBase, Module, \
    ReportModule, ReportAppConfig
from corehq.apps.builds.models import BuildSpec
from corehq.apps.domain.shortcuts import create_domain


class AppManagerTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build1 = {'version': '1.2.dev', 'build_number': 7106}
        cls.build2 = {'version': '2.7.0', 'build_number': 20655}

        add_build(**cls.build1)
        add_build(**cls.build2)

        cls.domain = 'test-domain'
        create_domain(cls.domain)

        with codecs.open(os.path.join(os.path.dirname(__file__), "data", "itext_form.xml"), encoding='utf-8') as f:
            cls.xform_str = f.read()

    def setUp(self):
        self.app = Application.new_app(self.domain, "TestApp", application_version=APP_V1)

        for i in range(3):
            module = self.app.add_module(Module.new_module("Module%d" % i, "en"))
            for j in range(3):
                self.app.new_form(module.id, name="Form%s-%s" % (i,j), attachment=self.xform_str, lang="en")
            module = self.app.get_module(i)
            detail = module.ref_details.short
            detail.columns.append(
                DetailColumn(header={"en": "test"}, model="case", field="test", format="plain")
            )
            detail.columns.append(
                DetailColumn(header={"en": "age"}, model="case", field="age", format="years-ago")
            )
        self.app.save()

    def test_increment_version(self):
        old_version = self.app.version
        self.app.save()
        self.assertEqual(self.app.version, old_version + 1)

    def tearDown(self):
        self.app.delete()

    def testSetUp(self):
        self.assertEqual(len(self.app.modules), 3)
        for module in self.app.get_modules():
            self.assertEqual(len(module.forms), 3)

    def testCreateJadJar(self):
        # make sure this doesn't raise an error
        self.app.build_spec = BuildSpec(**self.build1)
        self.app.create_build_files()

    def testDeleteForm(self):
        self.app.delete_form(self.app.modules[0].unique_id,
                             self.app.modules[0].forms[0].unique_id)
        self.assertEqual(len(self.app.modules), 3)
        for module, i in zip(self.app.get_modules(), [2,3,3]):
            self.assertEqual(len(module.forms), i)

    def testDeleteModule(self):
        self.app.delete_module(self.app.modules[0].unique_id)
        self.assertEqual(len(self.app.modules), 2)

    def testSwapModules(self):
        m0 = self.app.modules[0].name['en']
        m1 = self.app.modules[1].name['en']
        self.app.rearrange_modules(0,1)
        self.assertEqual(self.app.modules[0].name['en'], m1)
        self.assertEqual(self.app.modules[1].name['en'], m0)

    @patch_default_builds
    def _test_import_app(self, app_id_or_source):
        new_app = import_app(app_id_or_source, self.domain)
        self.assertEqual(set(new_app._attachments.keys()).intersection(self.app._attachments.keys()), set())
        new_forms = list(new_app.get_forms())
        old_forms = list(self.app.get_forms())
        for new_form, old_form in zip(new_forms, old_forms):
            self.assertEqual(new_form.source, old_form.source)
            self.assertNotEqual(new_form.unique_id, old_form.unique_id)

    def testImportApp_from_id(self):
        self.assertTrue(self.app._attachments)
        self._test_import_app(self.app.id)

    def testImportApp_from_source(self):
        app_source = Application.get_db().get(self.app.id)
        self._test_import_app(app_source)

    def testAppsBrief(self):
        """Test that ApplicationBase can wrap the
        truncated version returned by applications_brief
        """
        self.app.save()
        apps = ApplicationBase.get_db().view('app_manager/applications_brief',
            startkey=[self.domain],
            limit=1,
        ).all()
        self.assertEqual(len(apps), 1)

    @property
    @memoized
    def _yesno_source(self):
        # this app fixture uses both the (new) '_attachment'
        # and the (old) 'contents' conventions, to test that both work
        with open(os.path.join(os.path.dirname(__file__), 'data', 'yesno.json')) as f:
            return json.load(f)

    def _check_has_build_files(self, build):

        min_acceptable_paths = (
            'CommCare.jar',
            'CommCare.jad',
            'files/profile.ccpr',
            'files/profile.xml',
            'files/modules-0/forms-0.xml',
        )
        for path in min_acceptable_paths:
            self.assertTrue(build.fetch_attachment(path))

    def _check_legacy_odk_files(self, build):
        self.assertTrue(build.copy_of)
        with self.assertRaises(AttributeError):
            build.odk_profile_created_after_build
        path = 'files/profile.ccpr'
        build_version = build.version
        build.delete_attachment(path)
        add_odk_profile_after_build(build)
        build.save()
        build = Application.get(build.get_id)
        self.assertEqual(build.version, build_version)
        self.assertTrue(build.fetch_attachment(path))
        self.assertEqual(build.odk_profile_created_after_build, True)

    def testBuildApp(self):
        # do it from a NOT-SAVED app;
        # regression test against case where contents gets lazy-put w/o saving
        app = Application.wrap(self._yesno_source)
        self.assertEqual(app['_id'], None)  # i.e. hasn't been saved
        app._id = Application.get_db().server.next_uuid()
        copy = app.make_build()
        copy.save()
        self._check_has_build_files(copy)
        self._check_legacy_odk_files(copy)

    @patch_default_builds
    def testBuildImportedApp(self):
        app = import_app(self._yesno_source, self.domain)
        copy = app.make_build()
        copy.save()
        self._check_has_build_files(copy)
        self._check_legacy_odk_files(copy)

    def testRevertToCopy(self):
        old_name = 'old name'
        new_name = 'new name'
        app = Application.wrap(self._yesno_source)
        app.name = old_name
        app.save()

        copy = app.make_build()
        copy.save()

        self.assertEqual(copy.name, old_name)

        app.name = new_name
        app.save()
        app = Application.get(app.get_id)
        self.assertEqual(app.name, new_name)

        app = app.make_reversion_to_copy(copy)
        app.save()
        self.assertEqual(app.name, old_name)

    def testUserReg(self):
        "regression test for not catching ResourceNotFound"
        self.app.show_user_registration = True
        list(self.app.get_forms())

    def test_jad_settings(self):
        self.app.build_spec = BuildSpec(version='2.2.0', build_number=1)
        self.assertIn('Build-Number', self.app.jad_settings)
        self.app.build_spec = BuildSpec(version='2.8.0', build_number=1)
        self.assertNotIn('Build-Number', self.app.jad_settings)


class TestReportModule(SimpleTestCase):
    def test_report_module_uuid_updates(self):
        app = Application.new_app('domain', "Untitled Application", application_version=APP_V2)

        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.unique_id = 'report_module'

        report_app_config = ReportAppConfig(report_id='123',
                                            header={'en': 'CommBugz'})
        report_module.report_configs = [report_app_config]
        report_module._loaded = True

        app_source = app.export_json(dump_json=False)
        new_uuid = app_source['modules'][0]['report_configs'][0]['uuid']
        self.assertNotEqual(report_app_config.uuid, new_uuid)
