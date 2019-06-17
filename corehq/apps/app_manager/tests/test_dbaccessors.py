from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit.exceptions import NoResultFound
from django.test import TestCase
from corehq.apps.app_manager.dbaccessors import (
    domain_has_apps,
    get_all_app_ids,
    get_all_built_app_ids_and_versions,
    get_app,
    get_apps_in_domain,
    get_brief_apps_in_domain,
    get_build_doc_by_version,
    get_build_ids,
    get_build_ids_after_version,
    get_built_app_ids_with_submissions_for_app_id,
    get_built_app_ids_with_submissions_for_app_ids_and_versions,
    get_current_app,
    get_latest_build_doc,
    get_latest_app_ids_and_versions,
    get_latest_released_app_doc,
    get_apps_by_id,
    get_brief_app, get_latest_released_app_version, get_app_ids_in_domain)
from corehq.apps.app_manager.models import Application, RemoteApp, Module
from corehq.apps.domain.models import Domain
from corehq.util.test_utils import DocTestMixin


class DBAccessorsTest(TestCase, DocTestMixin):
    domain = 'app-manager-dbaccessors-test'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
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
            Application(
                domain=cls.domain,
                copy_of=cls.apps[0].get_id,
                version=cls.first_saved_version,
                has_submissions=True,
            ),
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
        super(DBAccessorsTest, cls).tearDownClass()

    @staticmethod
    def _make_app_brief(app):
        cls = app.__class__
        app_json = app.to_json()
        del app_json['_rev']
        app_json.pop('modules', None)
        # ApplicationBase.wrap does weird things, so I'm calling the __init__ directly
        # It may not matter, but it removes a potential source of error for the test
        return cls(app_json)

    def assert_docs_equal(self, doc1, doc2):
        del doc1['last_modified']
        del doc2['last_modified']
        super(DBAccessorsTest, self).assert_docs_equal(doc1, doc2)

    def test_get_brief_apps_in_domain(self):
        apps = get_brief_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 2)
        normal_app, remote_app = sorted(apps, key=lambda app: app.is_remote_app())
        expected_normal_app, expected_remote_app = sorted(self.apps, key=lambda app: app.is_remote_app())

        brief_remote = self._make_app_brief(expected_remote_app)

        brief_normal_app = self._make_app_brief(expected_normal_app)

        self.assert_docs_equal(remote_app, brief_remote)
        self.assert_docs_equal(normal_app, brief_normal_app)

    def test_get_brief_app(self):
        self.apps[0].save()
        brief_app = get_brief_app(self.domain, self.apps[0]._id)
        self.assertIsNotNone(brief_app)

        exepcted_app = self._make_app_brief(self.apps[0])
        self.assert_docs_equal(brief_app, exepcted_app)

    def test_get_brief_app_not_found(self):
        with self.assertRaises(NoResultFound):
            get_brief_app(self.domain, 'missing')

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
        brief_app = self._make_app_brief(expected_normal_app)
        self.assert_docs_equal(normal_app, brief_app)

    def test_get_apps_in_domain_exclude_remote(self):
        apps = get_apps_in_domain(self.domain, include_remote=False)
        self.assertEqual(len(apps), 1)
        normal_app, = apps
        expected_normal_app, _ = sorted(self.apps, key=lambda app: app.is_remote_app())
        self.assert_docs_equal(normal_app, expected_normal_app)

    def test_domain_has_apps(self):
        self.assertEqual(domain_has_apps(self.domain), True)
        self.assertEqual(domain_has_apps('somecrazydomainthathasnoapps'), False)

    def test_get_build_ids(self):
        app_ids = get_build_ids(self.domain, self.apps[0].get_id)
        self.assertEqual(len(app_ids), 2)

    def test_get_build_ids_after_version(self):
        app_ids = get_build_ids_after_version(self.domain, self.apps[0].get_id, self.first_saved_version)
        self.assertEqual(len(app_ids), 1)
        self.assertEqual(self.decoy_apps[1].get_id, app_ids[0])

    def test_get_built_app_ids_with_submissions_for_app_id(self):
        app_ids = get_built_app_ids_with_submissions_for_app_id(self.domain, self.apps[0].get_id)
        self.assertEqual(len(app_ids), 1)  # Should get the one that has_submissions

        app_ids = get_built_app_ids_with_submissions_for_app_id(
            self.domain,
            self.apps[0].get_id,
            self.first_saved_version
        )
        self.assertEqual(len(app_ids), 0)  # Should skip the one that has_submissions

    def test_get_built_app_ids_with_submissions_for_app_ids_and_versions(self):
        app_ids_in_domain = get_app_ids_in_domain(self.domain)
        app_ids = get_built_app_ids_with_submissions_for_app_ids_and_versions(
            self.domain,
            app_ids_in_domain,
            {self.apps[0]._id: self.first_saved_version},
        )
        self.assertEqual(len(app_ids), 0)  # Should skip the one that has_submissions

        app_ids = get_built_app_ids_with_submissions_for_app_ids_and_versions(
            self.domain, app_ids_in_domain
        )
        self.assertEqual(len(app_ids), 1)  # Should get the one that has_submissions

    def test_get_all_app_ids_for_domain(self):
        app_ids = get_all_app_ids(self.domain)
        self.assertEqual(len(app_ids), 3)

    def test_get_latest_built_app_ids_and_versions(self):
        build_ids_and_versions = get_latest_app_ids_and_versions(self.domain)
        self.assertEqual(build_ids_and_versions, {
            self.apps[0].get_id: self.apps[0].version,
            self.apps[1].get_id: self.apps[1].version,
        })

    def test_get_latest_built_app_ids_and_versions_with_app_id(self):
        build_ids_and_versions = get_latest_app_ids_and_versions(self.domain, self.apps[0].get_id)
        self.assertEqual(build_ids_and_versions, {
            self.apps[0].get_id: self.apps[0].version,
        })

    def test_get_all_built_app_ids_and_versions(self):
        app_build_versions = get_all_built_app_ids_and_versions(self.domain)

        self.assertEqual(len(app_build_versions), 3)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id == '1234']), 1)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id == self.apps[0]._id]), 2)

    def test_get_all_built_app_ids_and_versions_by_app(self):
        app_build_versions = get_all_built_app_ids_and_versions(self.domain, app_id='1234')

        self.assertEqual(len(app_build_versions), 1)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id == '1234']), 1)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id != '1234']), 0)


class TestAppGetters(TestCase):
    domain = 'test-app-getters'

    @classmethod
    def setUpClass(cls):
        super(TestAppGetters, cls).setUpClass()
        cls.project = Domain(name=cls.domain)
        cls.project.save()

        app_doc = Application(
            domain=cls.domain,
            name='foo',
            langs=["en"],
            version=1,
            modules=[Module()]
        ).to_json()
        app = Application.wrap(app_doc)  # app is v1

        app.save()  # app is v2
        cls.v2_build = app.make_build()
        cls.v2_build.is_released = True
        cls.v2_build.save()  # There is a starred build at v2

        app.save()  # app is v3
        app.make_build().save()  # There is a build at v3

        app.save()  # app is v4
        cls.app_id = app._id

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestAppGetters, cls).tearDownClass()

    def test_get_app_current(self):
        app = get_app(self.domain, self.app_id)
        self.assertEqual(app.version, 4)

    def test_get_current_app(self):
        app_doc = get_current_app(self.domain, self.app_id)
        self.assertEqual(app_doc['version'], 4)

    def test_latest_saved_from_build(self):
        app_doc = get_app(self.domain, self.v2_build._id, latest=True, target='save')
        self.assertEqual(app_doc['version'], 4)

    def test_get_app_latest_released_build(self):
        app = get_app(self.domain, self.app_id, latest=True)
        self.assertEqual(app.version, 2)

    def test_get_latest_released_app_doc(self):
        app_doc = get_latest_released_app_doc(self.domain, self.app_id)
        self.assertEqual(app_doc['version'], 2)

    def test_get_app_latest_build(self):
        app = get_app(self.domain, self.app_id, latest=True, target='build')
        self.assertEqual(app.version, 3)

    def test_get_latest_build_doc(self):
        app_doc = get_latest_build_doc(self.domain, self.app_id)
        self.assertEqual(app_doc['version'], 3)

    def test_get_specific_version(self):
        app_doc = get_build_doc_by_version(self.domain, self.app_id, version=2)
        self.assertEqual(app_doc['version'], 2)

    def test_get_apps_by_id(self):
        apps = get_apps_by_id(self.domain, [self.app_id])
        self.assertEqual(1, len(apps))
        self.assertEqual(apps[0].version, 4)

    def test_get_latest_released_app_version(self):
        version = get_latest_released_app_version(self.domain, self.app_id)
        self.assertEqual(version, 2)
