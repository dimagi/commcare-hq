# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hqadmin', '0005_auto_20160715_1612'),
    ]

    operations = [
        migrations.CreateModel(
            name='ESRestorePillowCheckpoints',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('seq', models.TextField()),
                ('checkpoint_id', models.CharField(max_length=255, db_index=True)),
                ('date_updated', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
