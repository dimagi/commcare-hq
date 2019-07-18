# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import uuid

from mock import patch
from memoized import memoized
import os
import codecs

from django.test import TestCase, SimpleTestCase

from corehq.apps.app_manager.dbaccessors import get_app, get_built_app_ids_for_app_id
from corehq.apps.app_manager.models import Application, DetailColumn, import_app, APP_V1, ApplicationBase, Module, \
    ReportModule, ReportAppConfig
from corehq.apps.app_manager.tasks import make_async_build_v2, prune_auto_generated_builds
from corehq.apps.app_manager.tests.util import add_build, patch_default_builds
from corehq.apps.app_manager.util import add_odk_profile_after_build, purge_report_from_mobile_ucr
from corehq.apps.builds.models import BuildSpec
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.tests.utils import get_sample_report_config
from corehq.util.test_utils import flag_enabled

from six.moves import zip
from six.moves import range
from io import open


class AppManagerTest(TestCase):
    min_paths = (
        'files/profile.ccpr',
        'files/profile.xml',
        'files/suite.xml',
        'files/media_suite.xml',
        'files/modules-0/forms-0.xml',
    )
    jad_jar_paths = (
        'CommCare.jar',
        'CommCare.jad',
    )

    @classmethod
    def setUpClass(cls):
        super(AppManagerTest, cls).setUpClass()
        cls.build1 = {'version': '1.2.0', 'build_number': 7106}
        cls.build2 = {'version': '2.7.0', 'build_number': 20655}

        add_build(**cls.build1)
        add_build(**cls.build2)

        cls.domain = 'test-domain'
        create_domain(cls.domain)

        with codecs.open(os.path.join(os.path.dirname(__file__), "data", "very_simple_form.xml"), encoding='utf-8') as f:
            cls.xform_str = f.read()

    def setUp(self):
        super(AppManagerTest, self).setUp()
        self.app = Application.new_app(self.domain, "TestApp")

        for i in range(3):
            module = self.app.add_module(Module.new_module("Module%d" % i, "en"))
            for j in range(3):
                self.app.new_form(module.id, name="Form%s-%s" % (i, j), attachment=self.xform_str, lang="en")
            module = self.app.get_module(i)
            detail = module.ref_details.short
            detail.columns.append(
                DetailColumn(header={"en": "test 字 unicode"}, model="case", field="test", format="plain")
            )
            detail.columns.append(
                DetailColumn(header={"en": "age"}, model="case", field="age", format="years-ago")
            )
        self.app.save()

    def test_last_modified(self):
        lm = self.app.last_modified
        self.app.save()
        app = Application.get(self.app._id)
        self.assertGreater(app.last_modified, lm)

    def test_last_modified_bulk(self):
        lm = self.app.last_modified
        Application.save_docs([self.app])
        app = Application.get(self.app._id)
        self.assertGreater(app.last_modified, lm)

        lm = self.app.last_modified
        Application.bulk_save([self.app])
        app = Application.get(self.app._id)
        self.assertGreater(app.last_modified, lm)

    def test_increment_version(self):
        old_version = self.app.version
        self.app.save()
        self.assertEqual(self.app.version, old_version + 1)

    def tearDown(self):
        self.app.delete()
        super(AppManagerTest, self).tearDown()

    def testSetUp(self):
        self.assertEqual(len(self.app.modules), 3)
        for module in self.app.get_modules():
            self.assertEqual(len(module.forms), 3)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def testCreateJadJar(self, mock):
        self.app.build_spec = BuildSpec(**self.build1)
        self.app.create_build_files()
        self.app.save(increment_version=False)
        # get a fresh one from the db to make sure attachments aren't cached
        # since that's closer to the real situation
        self.app = Application.get(self.app._id)
        self.app.create_jadjar_from_build_files(save=True)
        self.app.save(increment_version=False)
        self._check_has_build_files(self.app, self.jad_jar_paths)

    def testDeleteForm(self):
        self.app.delete_form(self.app.modules[0].unique_id,
                             self.app.modules[0].forms[0].unique_id)
        self.assertEqual(len(self.app.modules), 3)
        for module, i in zip(self.app.get_modules(), [2, 3, 3]):
            self.assertEqual(len(module.forms), i)

    def testDeleteModule(self):
        self.app.delete_module(self.app.modules[0].unique_id)
        self.assertEqual(len(self.app.modules), 2)

    def assertModuleOrder(self, actual_modules, expected_modules):
        self.assertEqual([m.name['en'] for m in actual_modules],
                         [m.name['en'] for m in expected_modules])

    def testSwapModules(self):
        m0, m1, m2 = self.app.modules
        self.app.rearrange_modules(1, 0)
        self.assertModuleOrder(self.app.modules, [m1, m0, m2])

    def testRearrangeModuleWithChildrenHigher(self):
        m0, m1, m2 = self.app.modules
        m2.root_module_id = m1.unique_id
        self.app.rearrange_modules(1, 0)
        # m2 is a child of m1, so when m1 moves to the top, m2 should follow
        self.assertModuleOrder(self.app.modules, [m1, m2, m0])

    def testRearrangeModuleWithChildrenLower(self):
        m0, m1, m2 = self.app.modules
        m1.root_module_id = m0.unique_id
        self.app.rearrange_modules(0, 1)
        self.assertModuleOrder(self.app.modules, [m2, m0, m1])

    @patch_default_builds
    def _test_import_app(self, app_id_or_source):
        new_app = import_app(app_id_or_source, self.domain)
        self.assertEqual(set(new_app.blobs.keys()).intersection(list(self.app.blobs.keys())), set())
        new_forms = list(new_app.get_forms())
        old_forms = list(self.app.get_forms())
        for new_form, old_form in zip(new_forms, old_forms):
            self.assertEqual(new_form.source, old_form.source)
            self.assertNotEqual(new_form.unique_id, old_form.unique_id)
        for new_module, old_module in zip(new_app.get_modules(), self.app.get_modules()):
            if isinstance(old_module, ReportModule):
                old_config_ids = {config.uuid for config in old_module.report_configs}
                new_config_ids = {config.uuid for config in new_module.report_configs}
                self.assertEqual(old_config_ids.intersection(new_config_ids), set())

    def testImportApp_from_id(self):
        self.assertTrue(self.app.blobs)
        self._test_import_app(self.app.id)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    @patch('corehq.apps.app_manager.models.ReportAppConfig.report')
    def testImportApp_from_source(self, mock, report_mock):
        report_mock.return_value = get_sample_report_config()
        report_module = self.app.add_module(ReportModule.new_module('Reports', None))
        report_module.report_configs = [
            ReportAppConfig(report_id='config_id1', header={'en': 'CommBugz'}),
            ReportAppConfig(report_id='config_id2', header={'en': 'CommBugz'})
        ]
        app_source = self.app.export_json(dump_json=False)
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
        with open(os.path.join(os.path.dirname(__file__), 'data', 'yesno.json'), encoding='utf-8') as f:
            return json.load(f)

    def _check_has_build_files(self, build, paths):
        for path in paths:
            self.assertTrue(build.fetch_attachment(path))

    def _app_strings_files(self, build):
        paths = ['files/default/app_strings.txt']
        for lang in build.langs:
            paths.append('files/{}/app_strings.txt'.format(lang))
        return paths

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

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def testBuildApp(self, mock):
        # do it from a NOT-SAVED app;
        # regression test against case where contents gets lazy-put w/o saving
        app = Application.wrap(self._yesno_source)
        self.assertEqual(app['_id'], None)  # i.e. hasn't been saved
        app._id = uuid.uuid4().hex
        copy = app.make_build()
        copy.save()
        self._check_has_build_files(copy, self.min_paths)

        app_strings_files = self._app_strings_files(copy)
        self._check_has_build_files(copy, app_strings_files)
        for path in app_strings_files:
            lang = path.split("/")[1]
            data_path = os.path.join(os.path.dirname(__file__), 'data', 'yesno_{}_app_strings.txt'.format(lang))
            with open(data_path, encoding='utf-8') as f:
                self.assertEqual(f.read().strip(), copy.fetch_attachment(path).decode('utf-8').strip())

        self._check_legacy_odk_files(copy)

    @patch_default_builds
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def testBuildImportedApp(self, mock):
        app = import_app(self._yesno_source, self.domain)
        copy = app.make_build()
        copy.save()
        self._check_has_build_files(copy, self.min_paths)
        self._check_legacy_odk_files(copy)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def testPruneAutoGeneratedBuilds(self, mock):
        # Build #1, manually generated
        app = import_app(self._yesno_source, self.domain)
        for module in app.modules:
            module.get_or_create_unique_id()
        app.save()
        build1 = app.make_build()
        build1.save()
        self.assertFalse(build1.is_auto_generated)

        # Build #2, auto-generated
        app.save()
        make_async_build_v2(app.get_id, app.domain, app.version)
        build_ids = get_built_app_ids_for_app_id(app.domain, app.id)
        self.assertEqual(len(build_ids), 2)
        self.assertEqual(build_ids[0], build1.id)
        build2 = get_app(app.domain, build_ids[1])
        self.assertTrue(build2.is_auto_generated)

        # First prune: delete nothing because the auto build is the most recent
        prune_auto_generated_builds(self.domain, app.id)
        self.assertEqual(len(get_built_app_ids_for_app_id(app.domain, app.id)), 2)

        # Build #3, manually generated
        app.save()
        build3 = app.make_build()
        build3.save()

        # Release the auto-generated build and prune again, should still delete nothing
        build2.is_released = True
        build2.save()
        prune_auto_generated_builds(self.domain, app.id)
        self.assertEqual(len(get_built_app_ids_for_app_id(app.domain, app.id)), 3)

        # Un-release the auto-generated build and prune again, which should delete it
        build2.is_released = False
        build2.save()
        prune_auto_generated_builds(self.domain, app.id)
        build_ids = get_built_app_ids_for_app_id(app.domain, app.id)
        self.assertEqual(len(build_ids), 2)
        self.assertNotIn(build2.id, build_ids)

    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def testRevertToCopy(self, mock):
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

    def test_jad_settings(self):
        self.app.build_spec = BuildSpec(version='2.2.0', build_number=1)
        self.assertIn('Build-Number', self.app.jad_settings)
        self.app.build_spec = BuildSpec(version='2.8.0', build_number=1)
        self.assertNotIn('Build-Number', self.app.jad_settings)


class TestReportModule(SimpleTestCase):

    @flag_enabled('MOBILE_UCR')
    @patch('dimagi.ext.couchdbkit.Document.get_db')
    def test_purge_report_from_mobile_ucr(self, get_db):
        report_config = ReportConfiguration(domain='domain', config_id='foo1')
        report_config._id = "my_report_config"

        app = Application.new_app('domain', "App")
        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.report_configs = [
            ReportAppConfig(report_id=report_config._id, header={'en': 'CommBugz'}),
            ReportAppConfig(report_id='other_config_id', header={'en': 'CommBugz'})
        ]
        self.assertEqual(len(app.modules[0].report_configs), 2)

        with patch('corehq.apps.app_manager.util.get_apps_in_domain') as get_apps:
            get_apps.return_value = [app]
            # this will get called when report_config is deleted
            purge_report_from_mobile_ucr(report_config)

        self.assertEqual(len(app.modules[0].report_configs), 1)
