from django.core.management import call_command
from django.db import migrations

from corehq.privileges import CASE_LIST_EXPLORER
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_cle_to_pro_and_above(apps, schema_editor):
    call_command(
        'cchq_prbac_grandfather_privs',
        CASE_LIST_EXPLORER,
        skip_edition='Paused,Community,Standard',
        noinput=True,
    )


def _reverse():
    call_command(
        'cchq_prbac_revoke_privs',
        CASE_LIST_EXPLORER,
        skip_edition='Paused,Community,Standard',
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0076_location_owner_in_report_builder_priv'),
    ]

    operations = [
        migrations.RunPython(
            _add_cle_to_pro_and_above,
            reverse_code=_reverse,
        ),
    ]
