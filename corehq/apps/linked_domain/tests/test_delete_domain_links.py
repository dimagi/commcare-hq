from django.test import TestCase

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.linked_domain.applications import unlink_app, unlink_apps_in_domain


class UnlinkApplicationTest(TestCase):

    domain = 'unlink-app-test'

    def test_unlink_app_returns_none_if_not_linked(self):
        app = Application.new_app(self.domain, 'Application')
        app.save()
        self.addCleanup(app.delete)

        unlinked_app = unlink_app(app)

        self.assertIsNone(unlinked_app)

    def test_unlink_app_returns_regular_app_if_linked(self):
        linked_app = LinkedApplication.new_app(self.domain, 'Linked Application')
        linked_app.save()
        expected_app_id = linked_app._id

        unlinked_app = unlink_app(linked_app)
        self.addCleanup(unlinked_app.delete)

        # ensure new app is not linked, and converted properly
        self.assertEqual('Application', unlinked_app.get_doc_type())
        self.assertEqual(expected_app_id, unlinked_app._id)


class UnlinkApplicationsForDomainTests(TestCase):

    domain = 'unlink-apps-test'

    def test_unlink_apps_for_domain_successfully_unlinks_app(self):
        linked_app = LinkedApplication.new_app(self.domain, 'Linked')
        linked_app.save()
        expected_app_id = linked_app._id

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        # ensure new app exists that is not linked
        self.assertEqual('Application', unlinked_apps[0].get_doc_type())
        self.assertEqual(expected_app_id, unlinked_apps[0]._id)

    def test_unlink_apps_for_domain_processes_multiple_apps(self):
        linked_app1 = LinkedApplication.new_app(self.domain, 'Linked1')
        linked_app2 = LinkedApplication.new_app(self.domain, 'Linked2')
        linked_app1.save()
        linked_app2.save()

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(2, len(unlinked_apps))

    def test_unlink_apps_for_domain_only_processes_linked_apps(self):
        app = Application.new_app(self.domain, 'Original')
        linked_app = LinkedApplication.new_app(self.domain, 'Linked')
        app.save()
        self.addCleanup(app.delete)
        linked_app.save()
        expected_app_id = linked_app._id

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(1, len(unlinked_apps))
        self.assertEqual(expected_app_id, unlinked_apps[0]._id)

    def test_unlink_apps_for_domain_returns_zero_if_no_linked_apps(self):
        app = Application.new_app(self.domain, 'Original')
        app.save()
        self.addCleanup(app.delete)

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(0, len(unlinked_apps))
