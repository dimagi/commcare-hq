from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_location_owner_in_report_builder_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0075_application_error_report_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_location_owner_in_report_builder_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
