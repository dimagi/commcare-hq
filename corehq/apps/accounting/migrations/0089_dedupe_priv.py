from django.core.management import call_command
from django.db import migrations

from corehq.privileges import CASE_DEDUPE
from corehq.util.django_migrations import skip_on_fresh_install



@skip_on_fresh_install
def _add_dedupe_to_advanced_and_above(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        CASE_DEDUPE,
        skip_edition='Paused,Community,Standard,Pro',
        noinput=True,
    )


def _reverse(apps, schema_editor):
    call_command(
        'cchq_prbac_revoke_privs',
        CASE_DEDUPE,
        skip_edition='Paused,Community,Standard,Pro',
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )

    from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import Command
    Command.OLD_PRIVILEGES.append(CASE_DEDUPE)
    call_command('cchq_prbac_bootstrap')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0088_add_new_softwareplan_visibility'),
    ]

    operations = [
        migrations.RunPython(
            _add_dedupe_to_advanced_and_above,
            reverse_code=_reverse,
        ),
    ]
