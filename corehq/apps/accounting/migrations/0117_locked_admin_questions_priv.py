from django.core.management import call_command
from django.db import migrations

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import LOCKED_ADMIN_QUESTIONS

from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_privilege(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.FREE,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        LOCKED_ADMIN_QUESTIONS,
        skip_edition=skip_editions,
        noinput=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0116_creditadjustment_payment_type'),
    ]

    operations = [
        migrations.RunPython(
            _grandfather_privilege,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
