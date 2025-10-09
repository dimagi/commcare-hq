from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import DATA_DICT_TYPES
from corehq.util.django_migrations import skip_on_fresh_install


editions_below_adv = ','.join((
    SoftwarePlanEdition.PAUSED,
    SoftwarePlanEdition.FREE,
    SoftwarePlanEdition.STANDARD,
    SoftwarePlanEdition.PRO,
))


@skip_on_fresh_install
def _grandfather_data_dict_types_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        DATA_DICT_TYPES,
        skip_edition=editions_below_adv,
        noinput=True,
    )


def _revoke_data_dict_types_priv(apps, schema_editor):
    from corehq.apps.hqadmin.management.commands import cchq_prbac_bootstrap

    call_command(
        'cchq_prbac_revoke_privs',
        DATA_DICT_TYPES,
        skip_edition=editions_below_adv,
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )
    command = cchq_prbac_bootstrap.Command()
    command.OLD_PRIVILEGES.append(DATA_DICT_TYPES)
    call_command(command)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0110_alter_customerinvoicecommunicationhistory_communication_type_and_more'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_data_dict_types_priv,
            reverse_code=_revoke_data_dict_types_priv,
        ),
    ]
