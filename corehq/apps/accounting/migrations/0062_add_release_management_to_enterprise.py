from django.core.management import call_command
from django.db import migrations

from corehq.privileges import RELEASE_MANAGEMENT
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_release_management_to_enterprise(apps, schema_editor):
    call_command(
        'cchq_prbac_grandfather_privs',
        RELEASE_MANAGEMENT,
        skip_edition='Paused,Community,Standard,Pro,Advanced',
        noinput=True,
    )


def _reverse():
    call_command(
        'cchq_prbac_revoke_privs',
        RELEASE_MANAGEMENT,
        skip_edition='Paused,Community,Standard,Pro,Advanced',
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0061_remove_enterprise_v1'),
    ]

    operations = [
        migrations.RunPython(
            _add_release_management_to_enterprise,
            reverse_code=_reverse
        ),
    ]
