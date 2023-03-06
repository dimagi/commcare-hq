from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import REGEX_FIELD_VALIDATION
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_regex_field_validation_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # Regex Field Validation is Pro Plan and higher
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        REGEX_FIELD_VALIDATION,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0067_add_view_app_diff_priv'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_regex_field_validation_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
