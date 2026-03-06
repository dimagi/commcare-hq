from django.core.management.base import BaseCommand, CommandError

from dimagi.utils.couch.database import iter_bulk_delete

from corehq.apps.app_manager.dbaccessors import get_build_ids
from corehq.apps.app_manager.management.commands.helpers import (
    get_deleted_app_ids,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.util.couch import get_db_by_doc_type

# This command is meant to be used for QA Automation domains only.
# https://dimagi.atlassian.net/browse/SAAS-19294
# Created as an alternative to the feature flag `export_apps_use_elasticsearch` that we removed.
ALLOWED_DOMAINS = {
    'qa-automation',
    'qa-automation-prod'
}


class Command(BaseCommand):
    help = "Hard delete soft-deleted apps and their builds for specific domains"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help='Domain to hard delete apps from (must be in ALLOWED_DOMAINS)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, domain, **options):
        if domain not in ALLOWED_DOMAINS:
            raise CommandError(
                f"""Domain '{domain}' is not in ALLOWED_DOMAINS.
                Only QA Automation domains are allowed in this command.
                Allowed domains: {ALLOWED_DOMAINS}"""
            )

        dry_run = options['dry_run']
        db = Application.get_db()

        deleted_app_ids = get_deleted_app_ids(domain)
        if not deleted_app_ids:
            self.stdout.write(f"No deleted apps found in domain '{domain}'")
            return

        self.stdout.write(f"Found {len(deleted_app_ids)} deleted app(s) in domain '{domain}'")

        build_ids = []
        for app_id in deleted_app_ids:
            app_build_ids = get_build_ids(domain, app_id)
            build_ids.extend(app_build_ids)
            if app_build_ids:
                self.stdout.write(f"  App {app_id}: {len(app_build_ids)} build(s)")

        delete_record_ids = self._get_delete_record_ids(domain, deleted_app_ids)

        all_ids = deleted_app_ids + build_ids
        self.stdout.write(
            f"\nTotal to delete: {len(deleted_app_ids)} app(s), "
            f"{len(build_ids)} build(s), "
            f"{len(delete_record_ids)} delete record(s)"
        )

        if dry_run:
            self.stdout.write("\nDry run, nothing deleted.")
            return

        if delete_record_ids:
            iter_bulk_delete(db, delete_record_ids)
            DeletedCouchDoc.objects.filter(doc_id__in=delete_record_ids).delete()
            self.stdout.write(f"Deleted {len(delete_record_ids)} delete record(s)")

        if all_ids:
            count = iter_bulk_delete(db, all_ids)
            self.stdout.write(f"Hard deleted {count} app/build doc(s)")

        self.stdout.write("Done.")

    def _get_delete_record_ids(self, domain, deleted_app_ids):
        db = get_db_by_doc_type('DeleteApplicationRecord')
        record_ids = get_doc_ids_in_domain_by_type(
            domain, 'DeleteApplicationRecord', database=db
        )
        if not record_ids:
            return []

        from dimagi.utils.couch.database import iter_docs
        matching_ids = []
        for doc in iter_docs(db, record_ids):
            if doc.get('app_id') in deleted_app_ids:
                matching_ids.append(doc['_id'])
        return matching_ids
