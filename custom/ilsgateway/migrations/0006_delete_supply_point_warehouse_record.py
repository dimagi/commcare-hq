from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0005_add_pending_reporting_data_recalculation'),
    ]

    operations = [
        migrations.DeleteModel(
            name='SupplyPointWarehouseRecord',
        )
    ]
