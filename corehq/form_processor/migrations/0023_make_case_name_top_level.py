# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0022_set_default_value_for_case_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='commcarecasesql',
            name='name',
            field=models.CharField(max_length=255, null=True),
            preserve_default=True,
        ),
    ]
