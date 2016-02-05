from django.test import TestCase
from corehq.apps.app_manager.dbaccessors import (
    get_brief_apps_in_domain,
    get_apps_in_domain,
    domain_has_apps,
    get_built_app_ids_for_app_id,
    get_all_app_ids,
    get_latest_built_app_ids_and_versions,
    get_all_built_app_ids_and_versions,
)
from corehq.apps.app_manager.models import Application, RemoteApp, Module
from corehq.apps.domain.models import Domain
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    domain = 'app-manager-dbaccessors-test'
    dependent_apps = ['corehq.apps.domain', 'corehq.apps.tzmigration', 'corehq.couchapps']
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.project = Domain(name=cls.domain)
        cls.project.save()
        cls.first_saved_version = 2
        cls.apps = [
            # .wrap adds lots of stuff in, but is hard to call directly
            # this workaround seems to work
            Application.wrap(Application(domain=cls.domain, name='foo', version=1, modules=[Module()]).to_json()),
            RemoteApp.wrap(RemoteApp(domain=cls.domain, version=1, name='bar').to_json()),
        ]
        for app in cls.apps:
            app.save()

        cls.decoy_apps = [
            # this one is a build
            Application(domain=cls.domain, copy_of=cls.apps[0].get_id, version=cls.first_saved_version),
            # this one is another build
            Application(domain=cls.domain, copy_of=cls.apps[0].get_id, version=12),

            # this one is another app
            Application(domain=cls.domain, copy_of='1234', version=12),
            # this one is in the wrong domain
            Application(domain='decoy-domain', version=5)
        ]
        for app in cls.decoy_apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps + cls.decoy_apps:
            app.delete()
        # to circumvent domain.delete()'s recursive deletion that this test doesn't need
        Domain.get_db().delete_doc(cls.project)

    @staticmethod
    def _make_app_brief(app):
        cls = app.__class__
        app_json = app.to_json()
        del app_json['_rev']
        app_json.pop('modules', None)
        # ApplicationBase.wrap does weird things, so I'm calling the __init__ directly
        # It may not matter, but it removes a potential source of error for the test
        return cls(app_json)

    def test_get_brief_apps_in_domain(self):
        apps = get_brief_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 2)
        normal_app, remote_app = sorted(apps, key=lambda app: app.is_remote_app())
        expected_normal_app, expected_remote_app = sorted(self.apps, key=lambda app: app.is_remote_app())
        self.assert_docs_equal(remote_app, self._make_app_brief(expected_remote_app))
        self.assert_docs_equal(normal_app, self._make_app_brief(expected_normal_app))

    def test_get_apps_in_domain(self):
        apps = get_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 2)
        normal_app, remote_app = sorted(apps, key=lambda app: app.is_remote_app())
        expected_normal_app, expected_remote_app = sorted(self.apps, key=lambda app: app.is_remote_app())
        self.assert_docs_equal(remote_app, expected_remote_app)
        self.assert_docs_equal(normal_app, expected_normal_app)

    def test_get_brief_apps_exclude_remote(self):
        apps = get_brief_apps_in_domain(self.domain, include_remote=False)
        self.assertEqual(len(apps), 1)
        normal_app, = apps
        expected_normal_app, _ = sorted(self.apps, key=lambda app: app.is_remote_app())
        self.assert_docs_equal(normal_app, self._make_app_brief(expected_normal_app))

    def test_get_apps_in_domain_exclude_remote(self):
        apps = get_apps_in_domain(self.domain, include_remote=False)
        self.assertEqual(len(apps), 1)
        normal_app, = apps
        expected_normal_app, _ = sorted(self.apps, key=lambda app: app.is_remote_app())
        self.assert_docs_equal(normal_app, expected_normal_app)

    def test_domain_has_apps(self):
        self.assertEqual(domain_has_apps(self.domain), True)
        self.assertEqual(domain_has_apps('somecrazydomainthathasnoapps'), False)

    def test_get_built_app_ids_for_app_id(self):
        app_ids = get_built_app_ids_for_app_id(self.domain, self.apps[0].get_id)
        self.assertEqual(len(app_ids), 2)

        app_ids = get_built_app_ids_for_app_id(self.domain, self.apps[0].get_id, self.first_saved_version)
        self.assertEqual(len(app_ids), 1)
        self.assertEqual(self.decoy_apps[1].get_id, app_ids[0])

    def test_get_all_app_ids_for_domain(self):
        app_ids = get_all_app_ids(self.domain)
        self.assertEqual(len(app_ids), 3)

    def test_get_latest_built_app_ids_and_versions(self):
        build_ids_and_versions = get_latest_built_app_ids_and_versions(self.domain)
        self.assertEqual(build_ids_and_versions, {
            self.apps[0].get_id: 12,
            '1234': 12,
        })

    def test_get_latest_built_app_ids_and_versions_with_app_id(self):
        build_ids_and_versions = get_latest_built_app_ids_and_versions(self.domain, self.apps[0].get_id)
        self.assertEqual(build_ids_and_versions, {
            self.apps[0].get_id: 12,
        })

    def test_get_all_built_app_ids_and_versions(self):
        app_build_verions = get_all_built_app_ids_and_versions(self.domain)

        self.assertEqual(len(app_build_verions), 3)
        self.assertEqual(len(filter(lambda abv: abv.app_id == '1234', app_build_verions)), 1)
        self.assertEqual(len(filter(lambda abv: abv.app_id == self.apps[0]._id, app_build_verions)), 2)
