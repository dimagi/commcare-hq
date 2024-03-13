from django.core.management import call_command
from django.db import migrations
from django_prbac.models import Role

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.privileges import APPLICATION_ERROR_REPORT
from corehq.util.django_migrations import skip_on_fresh_install


@skip_on_fresh_install
def _grandfather_application_error_report_priv(apps, schema_editor):
    call_command('cchq_prbac_bootstrap')

    # APPLICATION_ERROR_REPORT is only Enterprise Plan
    skip_editions = ','.join((
        SoftwarePlanEdition.PAUSED,
        SoftwarePlanEdition.COMMUNITY,
        SoftwarePlanEdition.STANDARD,
        SoftwarePlanEdition.PRO,
        SoftwarePlanEdition.ADVANCED,
    ))
    call_command(
        'cchq_prbac_grandfather_privs',
        APPLICATION_ERROR_REPORT,
        skip_edition=skip_editions,
        noinput=True,
    )


# Feature currently exists for the Advanced Plan as well, so we need to revert this before
# re-applying a migration to put it on the correct plan
@skip_on_fresh_install
def _revert_application_error_report_priv(apps, schema_editor):
    # Removing the associated Role will also drop related Grants for this feature
    try:
        Role.objects.get(slug=APPLICATION_ERROR_REPORT).delete()
    except Role.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0081_billingaccount_bill_web_user'),
    ]

    operations = [
        migrations.RunPython(
            _revert_application_error_report_priv,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            _grandfather_application_error_report_priv,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
