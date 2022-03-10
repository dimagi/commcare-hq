from django.db import migrations

from corehq.util.django_migrations import run_once_off_migration


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_domainrequest'),
    ]

    operations = [
        run_once_off_migration(
            'migrate_roles_permissions_feb2019', required_commit='8e8243bc80964e6981fcb89a712776e9faf97397'
        )
    ]
