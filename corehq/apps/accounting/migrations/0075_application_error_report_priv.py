from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import APPLICATION_ERROR_REPORT
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_application_error_report_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # APPLICATION_ERROR_REPORT are Advanced Plan and higher
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        APPLICATION_ERROR_REPORT,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0074_filtered_bulk_user_download_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_application_error_report_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
