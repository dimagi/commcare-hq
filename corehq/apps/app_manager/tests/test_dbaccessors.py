from django.test import TestCase

from couchdbkit.exceptions import NoResultFound

from corehq.apps.app_manager.dbaccessors import (
    domain_has_apps,
    get_all_built_app_ids_and_versions,
    get_app,
    get_app_cached,
    get_app_ids_in_domain,
    get_apps_by_id,
    get_apps_in_domain,
    get_brief_app,
    get_brief_apps_in_domain,
    get_build_doc_by_version,
    get_build_ids,
    get_build_ids_after_version,
    get_built_app_ids_with_submissions_for_app_id,
    get_built_app_ids_with_submissions_for_app_ids_and_versions,
    get_current_app,
    get_latest_app_ids_and_versions,
    get_latest_build_doc,
    get_latest_released_app_doc,
    get_latest_released_app_version,
    get_latest_released_app_versions_by_app_id,
    get_case_type_app_module_count,
    get_case_types_for_app_build,
    get_case_types_from_apps,
)
from corehq.apps.app_manager.models import Application, Module, RemoteApp, LinkedApplication
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import get_simple_form, patch_validate_xform
from corehq.apps.domain.models import Domain
from corehq.util.test_utils import DocTestMixin, disable_quickcache
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.apps import app_adapter


class DBAccessorsTest(TestCase, DocTestMixin):
    domain = 'app-manager-dbaccessors-test'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super(DBAccessorsTest, cls).setUpClass()
        cls.project = Domain.get_or_create_with_name(cls.domain, is_active=True)
        cls.first_saved_version = 2

        cls.normal_app = Application.wrap(
            Application(domain=cls.domain, name='foo', version=1, modules=[Module()]).to_json()
        )
        cls.normal_app.save()

        cls.remote_app = RemoteApp.wrap(RemoteApp(domain=cls.domain, version=1, name='bar').to_json())
        cls.remote_app.save()

        cls.linked_app = LinkedApplication.wrap(
            LinkedApplication(domain=cls.domain, version=1, name='linked-app', upstream_app_id='abc123').to_json()
        )
        cls.linked_app.save()

        cls.decoy_apps = [
            # this one is a build
            Application(
                domain=cls.domain,
                copy_of=cls.normal_app.get_id,
                version=cls.first_saved_version,
                has_submissions=True,
            ),
            # this one is another build
            Application(domain=cls.domain, copy_of=cls.normal_app.get_id, version=12),

            # this one is another app
            Application(domain=cls.domain, copy_of='1234', version=12),
            # this one is in the wrong domain
            Application(domain='decoy-domain', version=5)
        ]
        for app in cls.decoy_apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in [cls.normal_app, cls.remote_app, cls.linked_app, *cls.decoy_apps]:
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
        # brief apps return upstream_app_id which only exists on LinkedApplication
        if app.doc_type != 'LinkedApplication':
            app_json['upstream_app_id'] = None
        # ApplicationBase.wrap does weird things, so I'm calling the __init__ directly
        # It may not matter, but it removes a potential source of error for the test
        return cls(app_json)

    def assert_docs_equal(self, doc1, doc2):
        del doc1['last_modified']
        del doc2['last_modified']
        super(DBAccessorsTest, self).assert_docs_equal(doc1, doc2)

    def test_get_brief_apps_in_domain(self):
        apps = get_brief_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 3)
        normal_app = list(filter(
            lambda app: not app.is_remote_app() and app.doc_type != 'LinkedApplication', apps
        ))[0]
        linked_app = list(filter(lambda app: app.doc_type == 'LinkedApplication', apps))[0]
        remote_app = list(filter(lambda app: app.is_remote_app(), apps))[0]

        brief_normal_app = self._make_app_brief(self.normal_app)
        brief_remote = self._make_app_brief(self.remote_app)
        brief_linked_app = self._make_app_brief(self.linked_app)

        self.assert_docs_equal(normal_app, brief_normal_app)
        self.assert_docs_equal(remote_app, brief_remote)
        self.assert_docs_equal(linked_app, brief_linked_app)

    def test_get_brief_app(self):
        brief_app = get_brief_app(self.domain, self.normal_app._id)
        self.assertIsNotNone(brief_app)

        expected_app = self._make_app_brief(self.normal_app)
        self.assert_docs_equal(brief_app, expected_app)

    def test_get_brief_app_not_found(self):
        with self.assertRaises(NoResultFound):
            get_brief_app(self.domain, 'missing')

    def test_get_apps_in_domain(self):
        apps = get_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 3)
        normal_app = list(filter(
            lambda app: not app.is_remote_app() and app.doc_type != 'LinkedApplication', apps
        ))[0]
        linked_app = list(filter(lambda app: app.doc_type == 'LinkedApplication', apps))[0]
        remote_app = list(filter(lambda app: app.is_remote_app(), apps))[0]

        self.assert_docs_equal(remote_app, self.remote_app)
        self.assert_docs_equal(normal_app, self.normal_app)
        self.assert_docs_equal(linked_app, self.linked_app)

    def test_get_brief_apps_exclude_remote(self):
        apps = get_brief_apps_in_domain(self.domain, include_remote=False)
        self.assertEqual(len(apps), 2)
        normal_app = list(filter(lambda app: app.doc_type != 'LinkedApplication', apps))[0]
        expected_brief_app = self._make_app_brief(self.normal_app)
        self.assert_docs_equal(expected_brief_app, normal_app)

    def test_get_brief_linked_app_returns_upstream_app_id(self):
        brief_linked_app = get_brief_app(self.domain, self.linked_app._id)
        brief_normal_app = get_brief_app(self.domain, self.normal_app._id)

        self.assertEqual('abc123', brief_linked_app.upstream_app_id)
        self.assertEqual(None, brief_normal_app.upstream_app_id)

    def test_get_apps_in_domain_exclude_remote(self):
        apps = get_apps_in_domain(self.domain, include_remote=False)
        self.assertEqual(len(apps), 2)
        normal_app = list(filter(
            lambda app: not app.is_remote_app() and app.doc_type != 'LinkedApplication', apps
        ))[0]
        linked_app = list(filter(lambda app: app.doc_type == 'LinkedApplication', apps))[0]
        self.assert_docs_equal(self.normal_app, normal_app)
        self.assert_docs_equal(self.linked_app, linked_app)

    def test_domain_has_apps(self):
        self.assertEqual(domain_has_apps(self.domain), True)
        self.assertEqual(domain_has_apps('somecrazydomainthathasnoapps'), False)

    def test_get_build_ids(self):
        app_ids = get_build_ids(self.domain, self.normal_app.get_id)
        self.assertEqual(len(app_ids), 2)

    def test_get_build_ids_after_version(self):
        app_ids = get_build_ids_after_version(self.domain, self.normal_app.get_id, self.first_saved_version)
        self.assertEqual(len(app_ids), 1)
        self.assertEqual(self.decoy_apps[1].get_id, app_ids[0])

    def test_get_built_app_ids_with_submissions_for_app_id(self):
        app_ids = get_built_app_ids_with_submissions_for_app_id(self.domain, self.normal_app.get_id)
        self.assertEqual(len(app_ids), 1)  # Should get the one that has_submissions

        app_ids = get_built_app_ids_with_submissions_for_app_id(
            self.domain,
            self.normal_app.get_id,
            self.first_saved_version
        )
        self.assertEqual(len(app_ids), 0)  # Should skip the one that has_submissions

    def test_get_built_app_ids_with_submissions_for_app_ids_and_versions(self):
        app_ids_in_domain = get_app_ids_in_domain(self.domain)
        app_ids = get_built_app_ids_with_submissions_for_app_ids_and_versions(
            self.domain,
            app_ids_in_domain,
            {self.normal_app._id: self.first_saved_version},
        )
        self.assertEqual(len(app_ids), 0)  # Should skip the one that has_submissions

        app_ids = get_built_app_ids_with_submissions_for_app_ids_and_versions(
            self.domain, app_ids_in_domain
        )
        self.assertEqual(len(app_ids), 1)  # Should get the one that has_submissions

    def test_get_latest_built_app_ids_and_versions(self):
        build_ids_and_versions = get_latest_app_ids_and_versions(self.domain)
        self.assertEqual(build_ids_and_versions, {
            self.normal_app.get_id: self.normal_app.version,
            self.remote_app.get_id: self.remote_app.version,
            self.linked_app.get_id: self.linked_app.version,
        })

    def test_get_latest_built_app_ids_and_versions_with_app_id(self):
        build_ids_and_versions = get_latest_app_ids_and_versions(self.domain, self.normal_app.get_id)
        self.assertEqual(build_ids_and_versions, {
            self.normal_app.get_id: self.normal_app.version,
        })

    def test_get_all_built_app_ids_and_versions(self):
        app_build_versions = get_all_built_app_ids_and_versions(self.domain)

        self.assertEqual(len(app_build_versions), 3)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id == '1234']), 1)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id == self.normal_app._id]), 2)

    def test_get_all_built_app_ids_and_versions_by_app(self):
        app_build_versions = get_all_built_app_ids_and_versions(self.domain, app_id='1234')

        self.assertEqual(len(app_build_versions), 1)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id == '1234']), 1)
        self.assertEqual(len([abv for abv in app_build_versions if abv.app_id != '1234']), 0)


@es_test(requires=[app_adapter], setup_class=True)
class TestAppGetters(TestCase):
    domain = 'test-app-getters'

    @classmethod
    @patch_validate_xform()
    def setUpClass(cls):
        super(TestAppGetters, cls).setUpClass()
        cls.project = Domain.get_or_create_with_name(cls.domain)

        factory = AppFactory(cls.domain, name='foo')
        m0, f0 = factory.new_basic_module("bar", "bar")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        app = factory.app
        app.version = 1

        # Make builds v1 - v5. Builds v2 and v4 are released.
        app.save()  # app is v2
        cls.v2_build = app.make_build()
        cls.v2_build.is_released = True
        cls.v2_build.save()

        app.save()  # app is v3
        app.make_build().save()

        app.save()  # app is v4
        cls.v4_build = app.make_build()
        cls.v4_build.is_released = True
        cls.v4_build.save()

        app.save()  # app is v5
        cls.app_id = app._id

        factory = AppFactory(cls.domain, name='other_app')
        factory.new_basic_module("case", "case")
        other_app = factory.app
        other_app.save()

        app_adapter.bulk_index([app, cls.v2_build, cls.v4_build, other_app], refresh=True)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestAppGetters, cls).tearDownClass()

    def test_get_app_current(self):
        app = get_app(self.domain, self.app_id)
        self.assertEqual(app.version, 5)

    def test_get_current_app(self):
        app_doc = get_current_app(self.domain, self.app_id)
        self.assertEqual(app_doc['version'], 5)

    def test_get_app_cached(self):
        app_doc = get_app_cached(self.domain, self.v2_build.get_id)
        self.assertEqual(app_doc['is_released'], True)

    def test_latest_saved_from_build(self):
        app_doc = get_app(self.domain, self.v2_build._id, latest=True, target='save')
        self.assertEqual(app_doc['version'], 5)

    def test_get_app_latest_released_build(self):
        app = get_app(self.domain, self.app_id, latest=True)
        self.assertEqual(app.version, 4)

    def test_get_latest_released_app_doc(self):
        app_doc = get_latest_released_app_doc(self.domain, self.app_id)
        self.assertEqual(app_doc['version'], 4)

    def test_get_app_latest_build(self):
        app = get_app(self.domain, self.app_id, latest=True, target='build')
        self.assertEqual(app.version, 4)

    def test_get_latest_build_doc(self):
        app_doc = get_latest_build_doc(self.domain, self.app_id)
        self.assertEqual(app_doc['version'], 4)

    def test_get_specific_version(self):
        app_doc = get_build_doc_by_version(self.domain, self.app_id, version=2)
        self.assertEqual(app_doc['version'], 2)

    def test_get_apps_by_id(self):
        apps = get_apps_by_id(self.domain, [self.app_id])
        self.assertEqual(1, len(apps))
        self.assertEqual(apps[0].version, 5)

    def test_get_latest_released_app_version(self):
        version = get_latest_released_app_version(self.domain, self.app_id)
        self.assertEqual(version, 4)

    @disable_quickcache
    def test_get_latest_released_app_versions_by_app_id(self):
        versions = get_latest_released_app_versions_by_app_id(self.domain)
        self.assertEqual(versions, {
            self.app_id: 4,
        })

    def test_get_case_type_app_module_count(self):
        res = get_case_type_app_module_count(self.domain)
        self.assertEqual(res, {'bar': 1, 'case': 1})

    def test_get_case_types_for_app_build(self):
        res = get_case_types_for_app_build(self.domain, self.app_id)
        self.assertEqual(res, {'bar'})

    def test_get_case_types_from_apps(self):
        res = get_case_types_from_apps(self.domain)
        self.assertEqual(res, {'bar', 'case'})
