# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0062_auto_20160905_0938'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='external_id',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
