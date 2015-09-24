from django.core.management import BaseCommand
from corehq.doctypemigrations.migrator_instances import get_migrator_by_slug


class Command(BaseCommand):
    """
    Example: ./manage.py run_doctype_migration user_db_migration

    """
    def handle(self, migrator_slug, *args, **options):
        migrator = get_migrator_by_slug(migrator_slug)
        migrator.phase_1_bulk_migrate()
