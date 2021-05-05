from couchdbkit import ResourceNotFound
from django.test import TestCase

from corehq.apps.app_manager.models import Application, LinkedApplication
from corehq.apps.linked_domain.applications import unlink_app


class UnlinkApplicationsTest(TestCase):

    def test_unlink_app_returns_none_if_not_linked(self):
        app = Application.new_app('domain', 'Application')
        app.save()
        self.addCleanup(app.delete)

        unlinked_app = unlink_app(app)

        self.assertIsNone(unlinked_app)

    def test_unlink_app_returns_regular_app_if_linked(self):
        linked_app = LinkedApplication.new_app('domain', 'Linked Application')
        # unlink_app will handle cleanup of this doc
        linked_app.save()
        old_app_id = linked_app._id

        unlinked_app = unlink_app(linked_app)
        self.addCleanup(unlinked_app.delete)

        # ensure linked_app is deleted
        with self.assertRaises(ResourceNotFound):
            LinkedApplication.get(old_app_id)

        # ensure new app is not linked
        self.assertEqual('Application', unlinked_app.get_doc_type())
