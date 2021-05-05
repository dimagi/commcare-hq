from couchdbkit import ResourceNotFound
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
        # unlink_app will handle cleanup of this doc
        linked_app.save()
        deleted_app_id = linked_app._id

        unlinked_app = unlink_app(linked_app)
        self.addCleanup(unlinked_app.delete)

        # ensure linked_app is deleted
        with self.assertRaises(ResourceNotFound):
            LinkedApplication.get(deleted_app_id)

        # ensure new app is not linked, and converted properly
        self.assertEqual('Application', unlinked_app.get_doc_type())
        self.assertEqual('Linked Application', unlinked_app.name)


class UnlinkApplicationsForDomainTests(TestCase):

    domain = 'unlink-apps-test'

    def test_unlink_apps_for_domain_succeeds(self):
        linked_app = LinkedApplication.new_app(self.domain, 'Linked')
        # unlink_apps_in_domain will handle cleanup of this doc
        linked_app.save()
        deleted_app_id = linked_app._id

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        # ensure linked apps are deleted
        with self.assertRaises(ResourceNotFound):
            LinkedApplication.get(deleted_app_id)

        # ensure new app exists that is not linked
        self.assertEqual('Application', unlinked_apps[0].get_doc_type())
        self.assertEqual('Linked', unlinked_apps[0].name)

    def test_unlink_multiple_apps_for_domain_succeeds(self):
        linked_app1 = LinkedApplication.new_app(self.domain, 'Linked1')
        linked_app2 = LinkedApplication.new_app(self.domain, 'Linked2')
        # unlink_apps_in_domain will handle cleanup of these docs
        linked_app1.save()
        linked_app2.save()

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(2, len(unlinked_apps))

    def test_unlink_apps_for_domain_fails_if_no_linked_apps(self):
        app = Application.new_app(self.domain, 'Original')
        app.save()
        self.addCleanup(app.delete)

        unlinked_apps = unlink_apps_in_domain(self.domain)
        for app in unlinked_apps:
            self.addCleanup(app.delete)

        self.assertEqual(0, len(unlinked_apps))
