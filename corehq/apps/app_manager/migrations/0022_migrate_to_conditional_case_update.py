from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):
    dependencies = [
        ('app_manager', '0021_migrate_case_search_itemset_ids'),
    ]

    operations = [
        prompt_for_historical_migration(
            "app_manager", get_migration_name(__file__), "3c47a08dad06c20f376b25ce2bcd4f307ff5f6e6")
    ]
