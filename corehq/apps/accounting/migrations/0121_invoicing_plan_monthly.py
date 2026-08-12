from django.db import migrations

from corehq.util.django_migrations import skip_on_fresh_install

# Spelled out rather than imported from InvoicingPlan, which is losing its
# other members in this same change. Migrations must not depend on the
# current state of the code.
MONTHLY = 'MONTHLY'


@skip_on_fresh_install
def _set_invoicing_plan_to_monthly(apps, schema_editor):
    """
    Normalize quarterly and yearly accounts ahead of removing those options.

    Nothing was ever billed on a quarterly or yearly customer invoice, so
    there is no charge to reconcile — only the setting to clear.
    """
    BillingAccount = apps.get_model('accounting', 'BillingAccount')
    BillingAccount.objects.exclude(invoicing_plan=MONTHLY).update(invoicing_plan=MONTHLY)


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0120_billingaccountdomainhistory'),
    ]

    operations = [
        migrations.RunPython(
            _set_invoicing_plan_to_monthly,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
