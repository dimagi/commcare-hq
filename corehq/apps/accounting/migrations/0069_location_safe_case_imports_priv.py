from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import LOCATION_SAFE_CASE_IMPORTS
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_location_safe_case_imports_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # Location Safe Case Imports is Advanced Plan and higher
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        LOCATION_SAFE_CASE_IMPORTS,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0068_regex_field_validation_privilege'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_location_safe_case_imports_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
