# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0005_casetype_fully_generated'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseproperty',
            name='group',
            field=models.TextField(default=b'', blank=True),
        ),
    ]
