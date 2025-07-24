from django.db import migrations
from django.core.management import call_command
from corehq.apps.data_dictionary.management.commands.refresh_data_dictionary import MIGRATION_SLUG
from corehq.util.django_migrations import skip_on_fresh_install
from corehq.apps.domain_migration_flags.api import (
    ALL_DOMAINS,
    get_migration_complete,
)


@skip_on_fresh_install
def refresh_data_dictionary(apps, schema_editor):
    if not get_migration_complete(ALL_DOMAINS, MIGRATION_SLUG):
        try:
            call_command("refresh_data_dictionary")
        except Exception as e:
            print("\n[Migration Instruction]")
            print("Migration step `refresh_data_dictionary` failed:")
            print(f"    {e}\n\n")
            print("This step is *resumable* and safe to retry.\n\n")
            print("To resume:")
            print("    ./manage.py refresh_data_dictionary")
            print("    ./manage.py migrate\n\n")
            print("If the failure was due to malformed domains or apps,")
            print("you can skip them by passing:")
            print("    --domain-to-skip <domain> --app-id-to-skip <app_id>")
            raise


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0016_remove_case_property_group_and_rename_group_obj_caseproperty_group'),
    ]

    operations = [
        migrations.RunPython(refresh_data_dictionary, migrations.RunPython.noop)
    ]
