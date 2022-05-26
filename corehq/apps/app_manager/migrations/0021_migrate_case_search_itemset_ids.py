from django.db import migrations

from corehq.util.django_migrations import prompt_for_historical_migration, get_migration_name


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0020_exchangeapplication_allow_blank_privilege'),
    ]

    operations = [
        prompt_for_historical_migration(
            'app_manager', get_migration_name(__file__),
            required_commit='116a6fc9556ac929e29a35fd2dfa673984820561'
        )
    ]
