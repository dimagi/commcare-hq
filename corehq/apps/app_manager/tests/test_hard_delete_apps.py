from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.cleanup.models import DeletedCouchDoc


DOMAIN = 'test-hard-delete-apps'


class TestHardDeleteApps(TestCase):

    def _create_app(self, name='Test App'):
        app = Application.wrap(
            Application(domain=DOMAIN, name=name, version=1, modules=[Module()]).to_json()
        )
        app.save()
        self.addCleanup(self._safe_delete, app._id)
        return app

    def _safe_delete(self, doc_id):
        try:
            Application.get_db().delete_doc(doc_id)
        except ResourceNotFound:
            pass

    def _create_build(self, app):
        build = Application.wrap(app.to_json())
        del build['_id']
        del build['_rev']
        build.copy_of = app._id
        build.version = app.version
        build.save()
        self.addCleanup(self._safe_delete, build._id)
        return build

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_disallowed_domain_raises_error(self):
        with self.assertRaises(CommandError):
            call_command('hard_delete_apps', 'not-allowed-domain')

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_no_deleted_apps(self):
        app = self._create_app()
        call_command('hard_delete_apps', DOMAIN)
        # App should still exist since it's not deleted
        doc = Application.get_db().get(app._id)
        self.assertEqual(doc['doc_type'], 'Application')

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_hard_delete_deleted_app(self):
        app = self._create_app()
        app.delete_app()
        app.save()

        call_command('hard_delete_apps', DOMAIN)

        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(app._id)

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_hard_delete_also_deletes_builds(self):
        app = self._create_app()
        build = self._create_build(app)
        build_id = build._id

        app.delete_app()
        app.save()

        call_command('hard_delete_apps', DOMAIN)

        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(app._id)
        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(build_id)

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_non_deleted_app_not_affected(self):
        deleted_app = self._create_app(name='Deleted App')
        active_app = self._create_app(name='Active App')

        deleted_app.delete_app()
        deleted_app.save()

        call_command('hard_delete_apps', DOMAIN)

        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(deleted_app._id)

        doc = Application.get_db().get(active_app._id)
        self.assertEqual(doc['doc_type'], 'Application')

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_dry_run_does_not_delete(self):
        app = self._create_app()
        app.delete_app()
        app.save()

        call_command('hard_delete_apps', DOMAIN, dry_run=True)

        doc = Application.get_db().get(app._id)
        self.assertEqual(doc['doc_type'], 'Application-Deleted')

    @patch(
        'corehq.apps.app_manager.management.commands.hard_delete_apps.ALLOWED_DOMAINS',
        [DOMAIN],
    )
    def test_delete_records_cleaned_up(self):
        app = self._create_app()
        record = app.delete_app()
        app.save()
        record_id = record._id

        # Verify delete record exists
        self.assertTrue(
            DeletedCouchDoc.objects.filter(doc_id=record_id).exists()
        )

        call_command('hard_delete_apps', DOMAIN)

        # Delete record should be cleaned up from both CouchDB and PostgreSQL
        with self.assertRaises(ResourceNotFound):
            Application.get_db().get(record_id)
        self.assertFalse(
            DeletedCouchDoc.objects.filter(doc_id=record_id).exists()
        )
