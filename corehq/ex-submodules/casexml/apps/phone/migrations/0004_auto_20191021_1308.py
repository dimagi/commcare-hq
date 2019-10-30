from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phone', '0003_auto_20190405_1752'),
    ]

    operations = [
        migrations.AlterField(
            model_name='synclogsql',
            name='error_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='synclogsql',
            name='log_format',
            field=models.CharField(choices=[('simplified', 'simplified'), ('livequery', 'livequery')], max_length=10),
        ),
        migrations.AddField(
            model_name='synclogsql',
            name='app_id',
            field=models.CharField(null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='synclogsql',
            name='device_id',
            field=models.CharField(null=True, max_length=255),
        ),
    ]
