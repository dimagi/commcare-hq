from django.db import migrations

from corehq.util.django_migrations import run_once_off_migration


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0020_exchangeapplication_allow_blank_privilege'),
    ]

    operations = [
        run_once_off_migration(
            'migrate_case_search_prompt_itemset_ids', required_commit='116a6fc9556ac929e29a35fd2dfa673984820561'
        )
    ]
