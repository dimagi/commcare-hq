from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_domainrequest'),
    ]

    operations = [
        prompt_for_historical_migration(
            'users', get_migration_name(__file__), required_commit='8e8243bc80964e6981fcb89a712776e9faf97397'
        )
    ]
