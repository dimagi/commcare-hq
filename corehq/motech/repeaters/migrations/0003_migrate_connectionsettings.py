from django.db import migrations

from corehq.util.django_migrations import get_migration_name, prompt_for_historical_migration


class Migration(migrations.Migration):

    dependencies = [
        ('repeaters', '0002_sqlrepeatrecord'),
        ('motech', '0007_auto_20200909_2138'),
    ]

    operations = [
        prompt_for_historical_migration(
            'repeaters',
            get_migration_name(__file__),
            'c4ed85ee538e31665a82caff1e2996772266c532'
        )
    ]
