from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0132_update_nic_view'),
    ]

    operations = [
        migrations.AddField(
            model_name='icdsauditentryrecord',
            name='response_code',
            field=models.IntegerField(null=True),
        )
    ]
