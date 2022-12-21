from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0027_role_permission_unique'),
    ]

    operations = [
        prompt_for_historical_migration(
            'users', get_migration_name(__file__),
            required_commit='4f5a5ef0a9b5ef9873a9b2dce5646d7aa881c416'
        )
    ]
