from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import DATA_FILE_DOWNLOAD
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_data_file_download_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # Data File Download / File Dropzone is Pro Plan and higher
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        DATA_FILE_DOWNLOAD,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0065_phone_apk_heartbeat_privs'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_data_file_download_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
