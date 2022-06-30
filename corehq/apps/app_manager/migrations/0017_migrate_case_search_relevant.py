from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0016_alter_exchangeapplication'),
    ]

    operations = [
        prompt_for_historical_migration(
            "app_manager", get_migration_name(__file__), "8b87df0e4a504101645faa536bed7bc9ca58761c")
    ]
