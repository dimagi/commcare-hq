from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import ENABLE_ALL_ADD_ONS
from corehq.util.django_migrations import skip_on_fresh_install

skip_editions = ','.join((
    SoftwarePlanEdition.PAUSED,
    SoftwarePlanEdition.FREE,
    SoftwarePlanEdition.STANDARD,
))


@skip_on_fresh_install
def _add_enable_all_add_ons_to_pro(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    call_command(
        'cchq_prbac_grandfather_privs',
        ENABLE_ALL_ADD_ONS,
        skip_edition=skip_editions,
        noinput=True,
    )


def _reverse(apps, schema_editor):
    call_command(
        'cchq_prbac_revoke_privs',
        ENABLE_ALL_ADD_ONS,
        skip_edition=skip_editions,
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )

    from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import Command
    Command.OLD_PRIVILEGES.append(ENABLE_ALL_ADD_ONS)
    call_command('cchq_prbac_bootstrap')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0108_subscription_auto_renew_and_more'),
    ]

    operations = [
        migrations.RunPython(
            _add_enable_all_add_ons_to_pro,
            reverse_code=_reverse,
        ),
    ]
