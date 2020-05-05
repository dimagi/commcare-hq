from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_domain_specific_notifications'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(max_length=10, choices=[('billing', 'Billing Notification'), ('info', 'Product Notification'), ('alert', 'Maintenance Notification')]),
        ),
    ]
