# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0006_locationfixtureconfiguration'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sqllocation',
            name='external_id',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='sqllocation',
            name='latitude',
            field=models.DecimalField(null=True, max_digits=20, decimal_places=10, blank=True),
        ),
        migrations.AlterField(
            model_name='sqllocation',
            name='longitude',
            field=models.DecimalField(null=True, max_digits=20, decimal_places=10, blank=True),
        ),
        migrations.AlterField(
            model_name='sqllocation',
            name='metadata',
            field=jsonfield.fields.JSONField(default=dict, blank=True),
        ),
        migrations.AlterField(
            model_name='sqllocation',
            name='supply_point_id',
            field=models.CharField(db_index=True, max_length=255, unique=True, null=True, blank=True),
        ),
    ]
