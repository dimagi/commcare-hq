from django.db import migrations

from corehq.util.django_migrations import block_upgrade_for_removed_migration


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0016_alter_exchangeapplication'),
    ]

    operations = [
        block_upgrade_for_removed_migration("8b87df0e4a504101645faa536bed7bc9ca58761c")
    ]
