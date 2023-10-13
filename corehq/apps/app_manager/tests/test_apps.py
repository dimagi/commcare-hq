import json
import os
import uuid
from datetime import datetime

from django.test import TestCase

from collections import namedtuple
from memoized import memoized
from unittest.mock import patch

from corehq.apps.app_manager.dbaccessors import get_app, get_build_ids
from corehq.apps.app_manager.models import (
    Application,
    ApplicationBase,
    DetailColumn,
    LinkedApplication,
    Module,
    ReportAppConfig,
    ReportModule,
    import_app,
)
from corehq.apps.app_manager.tasks import (
    autogenerate_build,
    prune_auto_generated_builds,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import (
    TestXmlMixin,
    add_build,
    patch_default_builds, get_simple_form, patch_validate_xform,
)
from corehq.apps.app_manager.util import add_odk_profile_after_build
from corehq.apps.app_manager.views.apps import load_app_from_slug
from corehq.apps.app_manager.views.utils import update_linked_app
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.linked_domain.applications import link_app
from corehq.apps.userreports.tests.utils import get_sample_report_config


MockRequest = namedtuple('MockRequest', ['status', 'data'])


@patch_validate_xform()
class AppManagerTest(TestCase, TestXmlMixin):
    file_path = ('data',)
    min_paths = (
        'files/profile.ccpr',
        'files/profile.xml',
        'files/suite.xml',
        'files/media_suite.xml',
        'files/modules-0/forms-0.xml',
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

        cls.xform_str = cls.get_xml('very_simple_form').decode('utf-8')

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

    def test_undo_delete_app_removes_deleted_couch_doc_record(self):
        rec = self.app.delete_app()
        self.app.save()
        obj = DeletedCouchDoc.objects.create(
            doc_id=self.app._id,
            doc_type=self.app.doc_type,
            deleted_on=datetime.utcnow(),
        )
        assert obj.doc_type.endswith("-Deleted"), obj.doc_type
        params = {'doc_id': rec._id, 'doc_type': rec.doc_type}
        assert DeletedCouchDoc.objects.get(**params)
        rec.undo()
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(**params)

    def testDeleteForm(self):
        self.app.delete_form(self.app.modules[0].unique_id,
                             self.app.modules[0].forms[0].unique_id)
        self.assertEqual(len(self.app.modules), 3)
        for module, i in zip(self.app.get_modules(), [2, 3, 3]):
            self.assertEqual(len(module.forms), i)

    def test_undo_delete_form_removes_deleted_couch_doc_record(self):
        form = self.app.modules[0].forms[0]
        rec = self.app.delete_form(self.app.modules[0].unique_id, form.unique_id)
        params = {'doc_id': rec._id, 'doc_type': rec.doc_type}
        assert DeletedCouchDoc.objects.get(**params)
        rec.undo()
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(**params)

    def testDeleteModule(self):
        self.app.delete_module(self.app.modules[0].unique_id)
        self.assertEqual(len(self.app.modules), 2)

    def test_undo_delete_module_removes_deleted_couch_doc_record(self):
        module = self.app.modules[0]
        rec = self.app.delete_module(module.unique_id)
        params = {'doc_id': rec._id, 'doc_type': rec.doc_type}
        assert DeletedCouchDoc.objects.get(**params)
        rec.undo()
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(**params)

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
        return new_app

    def testImportApp_from_id(self):
        self.assertTrue(self.app.blobs)
        imported_app = self._test_import_app(self.app.id)
        self.assertEqual(imported_app.family_id, self.app.id)

    @patch('corehq.apps.app_manager.models.ReportAppConfig.report')
    def testImportApp_from_source(self, report_mock):
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

    def testBuildApp(self):
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
    def testBuildImportedApp(self):
        app = import_app(self._yesno_source, self.domain)
        copy = app.make_build()
        copy.save()
        self._check_has_build_files(copy, self.min_paths)
        self._check_legacy_odk_files(copy)

    @patch('urllib3.PoolManager.request')
    def testBuildTemplateApps(self, request_mock):
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images',
                                  'commcare-hq-logo.png')
        with open(image_path, 'rb') as f:
            request_mock.return_value = MockRequest(status=200, data=f.read())

            # Tests that these apps successfully build
            for slug in ['agriculture', 'health', 'wash']:
                self.assertIsNotNone(load_app_from_slug(self.domain, 'username', slug))

    def testGetLatestBuild(self):
        factory = AppFactory(build_version='2.40.0')
        m0, f0 = factory.new_basic_module('register', 'case')
        f0.source = get_simple_form(xmlns=f0.unique_id)
        app = factory.app
        app.save()

        build1 = app.make_build()
        build1.save()
        # ensure that there was no previous version used during the build process
        self.assertEqual(app.get_latest_build.get_cache(app), {})
        self.assertEqual(build1.get_latest_build.get_cache(build1), {(): None})

        app.save()
        build2 = app.make_build()
        build2.save()
        # ensure that there was no previous version used during the build process
        self.assertEqual(app.get_latest_build.get_cache(app), {})
        self.assertEqual(build2.get_latest_build.get_cache(build2)[()].id, build1.id)

    def testPruneAutoGeneratedBuilds(self):
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
        autogenerate_build(app, "username")
        build_ids = get_build_ids(app.domain, app.id)
        self.assertEqual(len(build_ids), 2)
        self.assertEqual(build_ids[1], build1.id)
        build2 = get_app(app.domain, build_ids[0])
        self.assertTrue(build2.is_auto_generated)

        # First prune: delete nothing because the auto build is the most recent
        prune_auto_generated_builds(self.domain, app.id)
        self.assertEqual(len(get_build_ids(app.domain, app.id)), 2)

        # Build #3, manually generated
        app.save()
        build3 = app.make_build()
        build3.save()

        # Release the auto-generated build and prune again, should still delete nothing
        build2.is_released = True
        build2.save()
        prune_auto_generated_builds(self.domain, app.id)
        self.assertEqual(len(get_build_ids(app.domain, app.id)), 3)

        # Un-release the auto-generated build and prune again, which should delete it
        build2.is_released = False
        build2.save()
        prune_auto_generated_builds(self.domain, app.id)
        build_ids = get_build_ids(app.domain, app.id)
        self.assertEqual(len(build_ids), 2)
        self.assertNotIn(build2.id, build_ids)

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

    def testConvertToApplication(self):
        factory = AppFactory(build_version='2.40.0')
        m0, f0 = factory.new_basic_module('register', 'case')
        f0.source = get_simple_form(xmlns=f0.unique_id)
        factory.app.save()
        self.addCleanup(factory.app.delete)
        build = factory.app.make_build()
        build.is_released = True
        build.save()
        self.addCleanup(build.delete)

        linked_app = LinkedApplication()
        linked_app.domain = 'other-domain'
        linked_app.save()
        self.addCleanup(linked_app.delete)

        link_app(linked_app, factory.app.domain, factory.app.id)
        update_linked_app(linked_app, factory.app.id, 'system')

        unlinked_doc = linked_app.convert_to_application().to_json()
        self.assertEqual(unlinked_doc['doc_type'], 'Application')
        self.assertFalse(hasattr(unlinked_doc, 'linked_app_attrs'))
