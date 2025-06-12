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
    while not get_migration_complete(ALL_DOMAINS, MIGRATION_SLUG):
        call_command("refresh_data_dictionary")


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0016_remove_case_property_group_and_rename_group_obj_caseproperty_group'),
    ]

    operations = [
        migrations.RunPython(refresh_data_dictionary, migrations.RunPython.noop)
    ]
