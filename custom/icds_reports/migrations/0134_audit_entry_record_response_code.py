from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0133_auto_20191001_0835'),
    ]

    operations = [
        migrations.AddField(
            model_name='icdsauditentryrecord',
            name='response_code',
            field=models.IntegerField(null=True),
        )
    ]
