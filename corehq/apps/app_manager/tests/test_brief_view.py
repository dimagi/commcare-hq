from django.test import TestCase
from corehq.apps.app_manager.models import Application, RemoteApp, get_apps_in_domain
from corehq.apps.domain.shortcuts import create_domain


class BriefViewTest(TestCase):
    domain = 'application-brief-test'

    def setUp(self):
        self.project = create_domain(self.domain)
        self.apps = [
            Application(domain=self.domain),
            RemoteApp(domain=self.domain),
        ]
        for app in self.apps:
            app.save()

    def tearDown(self):
        for app in self.apps:
            app.delete()
        self.project.delete()

    def test_domain(self):
        apps = self.project.applications()
        self.assertEqual(len(apps), 2)

    def test_app_base(self):
        apps = get_apps_in_domain(self.domain)
        self.assertEqual(len(apps), 2)
