# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0004_auto_20161130_2125'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetype',
            name='fully_generated',
            field=models.BooleanField(default=False),
        ),
    ]
