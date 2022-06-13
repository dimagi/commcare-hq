from django.db import migrations

from corehq.util.django_migrations import block_upgrade_for_removed_migration


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0017_migrate_case_search_relevant'),
    ]

    operations = [
        block_upgrade_for_removed_migration("9cc207180e9ebde1c06a98f5e3da1c29b9d37dee"),
    ]
