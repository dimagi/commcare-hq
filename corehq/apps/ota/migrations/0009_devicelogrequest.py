from __future__ import absolute_import, unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ota', '0008_auto_20190108_1808'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceLogRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('username', models.CharField(max_length=255)),
                ('device_id', models.CharField(max_length=255)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
