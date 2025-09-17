from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import GEOJSON_EXPORT
from corehq.util.django_migrations import skip_on_fresh_install


skip_editions = ','.join((
    SoftwarePlanEdition.PAUSED,
    SoftwarePlanEdition.FREE,
    SoftwarePlanEdition.STANDARD,
    SoftwarePlanEdition.PRO,
))


@skip_on_fresh_install
def _grandfather_geojson_export_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')
    call_command(
        'cchq_prbac_grandfather_privs',
        GEOJSON_EXPORT,
        skip_edition=skip_editions,
        noinput=True,
    )


def _revoke_geojson_export_priv(apps, schema_editor):
    from corehq.apps.hqadmin.management.commands import cchq_prbac_bootstrap

    call_command(
        'cchq_prbac_revoke_privs',
        GEOJSON_EXPORT,
        skip_edition=skip_editions,
        delete_privs=False,
        check_privs_exist=True,
        noinput=True,
    )
    command = cchq_prbac_bootstrap.Command()
    command.OLD_PRIVILEGES.append(GEOJSON_EXPORT)
    call_command(command)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0108_subscription_auto_renew_and_more'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_geojson_export_priv,
            reverse_code=_revoke_geojson_export_priv,
        ),
    ]
