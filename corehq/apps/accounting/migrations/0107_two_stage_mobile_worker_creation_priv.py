from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION
from corehq.util.django_migrations import skip_on_fresh_install



@skip_on_fresh_install
def _add_data_cleaning_to_enterprise(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.FREE,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION,
        skip_edition=skip_editions,
        noinput=True,
    )


def _reverse(apps, schema_editor):
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.FREE,
    ))
    call_command(
        'cchq_prbac_revoke_privs',
        TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION,
        skip_edition=skip_editions,
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )

    from corehq.apps.hqadmin.management.commands.cchq_prbac_bootstrap import Command
    Command.OLD_PRIVILEGES.append(TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    call_command('cchq_prbac_bootstrap')


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0106_alter_billingcontactinfo_company_name'),
    ]

    operations = [
        migrations.RunPython(
            _add_data_cleaning_to_enterprise,
            reverse_code=_reverse,
        ),
    ]
