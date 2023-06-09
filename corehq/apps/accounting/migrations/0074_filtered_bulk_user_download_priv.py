from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import FILTERED_BULK_USER_DOWNLOAD
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_filtered_bulk_user_download_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # FILTERED_BULK_USER_DOWNLOAD are Advanced Plan and higher
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        FILTERED_BULK_USER_DOWNLOAD,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0073_export_ownership_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_filtered_bulk_user_download_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
