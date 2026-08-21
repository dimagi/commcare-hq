from django.db import migrations

# Matches the SQL Django itself emits for RemoveField, including CASCADE.
DROP_COLUMN = 'ALTER TABLE "accounting_billingaccount" DROP COLUMN "invoicing_plan" CASCADE;'

# Restores what 0122 left behind, database default included. Reversing only this
# migration lands back in 0122's world, where the model does not declare the
# field and the database is what satisfies NOT NULL — so unlike a reversed
# RemoveField, this must not drop the default. Reversing 0122 does that.
ADD_COLUMN = (
    'ALTER TABLE "accounting_billingaccount"'
    ' ADD COLUMN "invoicing_plan" varchar(25) DEFAULT \'MONTHLY\' NOT NULL;'
)


class Migration(migrations.Migration):
    """
    Drop the ``invoicing_plan`` column, undeclared in model state since 0122.

    Raw SQL rather than ``RemoveField`` because the field is already out of
    migration state; there is nothing left to remove from it.

    Must not be merged until 0122 is deployed everywhere. If both land in one
    deploy, migrations run while the release that still declares the field is
    serving, and every ``BillingAccount`` query fails until the code switch.
    """

    dependencies = [
        ('accounting', '0122_stop_declaring_invoicing_plan'),
    ]

    operations = [
        migrations.RunSQL(DROP_COLUMN, reverse_sql=ADD_COLUMN),
    ]
