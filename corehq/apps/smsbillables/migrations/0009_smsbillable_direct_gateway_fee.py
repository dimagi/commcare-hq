from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0008__multipart_count__non_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='smsbillable',
            name='direct_gateway_fee',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=4),
            preserve_default=True,
        ),
    ]
