from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0088_migrate_balance_4_switch_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='ledgertransaction',
                    name='updated_balance',
                    field=models.BigIntegerField(default=0),
                ),
            ]
        ),
    ]
