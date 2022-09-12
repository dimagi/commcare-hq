from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0017_migrate_case_search_relevant'),
    ]

    operations = [
        prompt_for_historical_migration(
            "app_manager", get_migration_name(__file__), "9cc207180e9ebde1c06a98f5e3da1c29b9d37dee"),
    ]
