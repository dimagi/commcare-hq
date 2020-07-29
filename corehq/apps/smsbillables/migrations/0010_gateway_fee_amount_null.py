from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0009_smsbillable_direct_gateway_fee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsgatewayfee',
            name='amount',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=4),
            preserve_default=True,
        ),
    ]
