from django.db import migrations

# The column is NOT NULL and Django keeps field defaults in Python, so once the
# model stops declaring the field every INSERT would omit it and violate the
# constraint. Hand the default to the database for as long as the column lives.
SET_DEFAULT = (
    'ALTER TABLE "accounting_billingaccount"'
    ' ALTER COLUMN "invoicing_plan" SET DEFAULT \'MONTHLY\';'
)
DROP_DEFAULT = (
    'ALTER TABLE "accounting_billingaccount"'
    ' ALTER COLUMN "invoicing_plan" DROP DEFAULT;'
)


class Migration(migrations.Migration):
    """
    Stop declaring ``BillingAccount.invoicing_plan``, leaving the column in place.

    Deploys run the new code's migrations and only then switch servers over to
    it, so dropping the column here would leave the still-running previous
    release selecting a column that no longer exists. Removing the field from
    migration state alone keeps every deploy state valid: the column is present
    throughout, and only the new code stops asking for it. A later migration
    drops the column, once no deployed code declares the field.

    Neither statement here rewrites the table; both are catalog-only.
    """

    dependencies = [
        ('accounting', '0121_invoicing_plan_monthly'),
    ]

    operations = [
        migrations.RunSQL(SET_DEFAULT, reverse_sql=DROP_DEFAULT),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='billingaccount',
                    name='invoicing_plan',
                ),
            ],
            database_operations=[],
        ),
    ]
