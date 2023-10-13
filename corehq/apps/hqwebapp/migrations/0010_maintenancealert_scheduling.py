from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0009_truncate_authtoken_table'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancealert',
            name='start_time',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='maintenancealert',
            name='end_time',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='maintenancealert',
            name='timezone',
            field=models.CharField(max_length=32, default='UTC'),
        ),
    ]
