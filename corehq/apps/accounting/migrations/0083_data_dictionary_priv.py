from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import DATA_DICTIONARY
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_data_dictionary_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # DATA_DICTIONARY are Advanced Plan and higher
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        DATA_DICTIONARY,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0082_application_error_report_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_data_dictionary_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
