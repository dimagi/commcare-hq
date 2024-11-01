from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0056_add_manage_domain_alerts_permission'),
    ]

    operations = [
        prompt_for_historical_migration(
            "users", get_migration_name(__file__), "1359e6ed5b12d929d97f5a59f0f0181a3811ccdc")
    ]
