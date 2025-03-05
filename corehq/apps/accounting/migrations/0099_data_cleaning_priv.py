from django.core.management import call_command
from django.db import migrations

from corehq.privileges import BULK_DATA_CLEANING
from corehq.util.django_migrations import skip_on_fresh_install



@skip_on_fresh_install
def _add_data_cleaning_to_enterprise(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        BULK_DATA_CLEANING,
        skip_edition='Paused,Community,Standard,Pro,Advanced',
        noinput=True,
    )


def _reverse(apps, schema_editor):
    call_command(
        'cchq_prbac_revoke_privs',
        BULK_DATA_CLEANING,
        skip_edition='Paused,Community,Standard,Pro,Advanced',
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )

    from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import Command
    Command.OLD_PRIVILEGES.append(BULK_DATA_CLEANING)
    call_command('cchq_prbac_bootstrap')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0098_app_dependencies_priv'),
    ]

    operations = [
        migrations.RunPython(
            _add_data_cleaning_to_enterprise,
            reverse_code=_reverse,
        ),
    ]
