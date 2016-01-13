from django.test import TestCase
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.app_manager.models import Application, RemoteApp, Module
from corehq.apps.domain.shortcuts import create_domain


class BriefViewTest(TestCase):
    domain = 'application-brief-test'

    @classmethod
    def setUpClass(cls):
        cls.project = create_domain(cls.domain)
        cls.apps = [
            Application(domain=cls.domain, modules=[Module()]),
            RemoteApp(domain=cls.domain),
        ]
        for app in cls.apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()
        cls.project.delete()

    def test_domain(self):
        apps = self.project.applications()
        self.assertEqual(len(apps), 2)

    def test_app_base(self):
        apps = get_brief_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 2)
        for app in apps:
            # assert that it is in fact the "brief" version
            if not app.is_remote_app():
                self.assertEqual(len(app.modules), 0)
