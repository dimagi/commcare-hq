
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0083_migrate_delta_4_switch_columns'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='ledgertransaction',
                    name='delta',
                    field=models.BigIntegerField(default=0),
                ),
            ]
        ),
    ]
