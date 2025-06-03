from django.core.management import call_command
from django.db import migrations

from corehq.privileges import BULK_DATA_EDITING
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _add_data_editing_to_advanced_and_clean_old_privilege(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # first remove the old privilege ("bulk_data_cleaning") if it exists
    call_command(
        'cchq_prbac_revoke_privs',
        "bulk_data_cleaning",
        delete_privs=True,
        check_privs_exist=False,
        noinput=True,
    )

    # then grandfather new privilege (Advanced + Enterprise)
    call_command(
        'cchq_prbac_grandfather_privs',
        BULK_DATA_EDITING,
        skip_edition='Paused,Community,Standard,Pro',
        noinput=True,
    )


def _reverse(apps, schema_editor):
    # grandfather the old privilege ("bulk_data_cleaning") to Advanced and Enterprise plans again
    call_command(
        'cchq_prbac_grandfather_privs',
        "bulk_data_cleaning",
        skip_edition='Paused,Community,Standard,Pro,Advanced',
        noinput=True,
    )
    # undo assigning the new privilege to Advanced and Enterprise plans
    call_command(
        'cchq_prbac_revoke_privs',
        BULK_DATA_EDITING,
        delete_privs=True,
        check_privs_exist=True,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0102_alter_defaultproductplan_edition_and_more'),
    ]

    operations = [
        migrations.RunPython(
            _add_data_editing_to_advanced_and_clean_old_privilege,
            reverse_code=_reverse,
        ),
    ]
