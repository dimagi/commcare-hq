from django.test import TestCase
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain, \
    get_apps_in_domain, domain_has_apps
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
        cls.apps = [
            # .wrap adds lots of stuff in, but is hard to call directly
            # this workaround seems to work
            Application.wrap(Application(domain=cls.domain, name='foo', modules=[Module()]).to_json()),
            RemoteApp.wrap(RemoteApp(domain=cls.domain, name='bar').to_json()),
        ]
        for app in cls.apps:
            app.save()

        cls.decoy_apps = [
            # this one is a build
            Application(domain=cls.domain, copy_of=cls.apps[0].get_id),
            # this one is in the wrong domain
            Application(domain='decoy-domain')
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

    def test_domain_has_apps(self):
        self.assertEqual(domain_has_apps(self.domain), True)
        self.assertEqual(domain_has_apps('somecrazydomainthathasnoapps'), False)
