# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0009_auto_20160413_1311'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deliverygroupreport',
            name='report_date',
            field=models.DateTimeField(default=datetime.datetime.utcnow),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='slabconfig',
            name='sql_location',
            field=models.OneToOneField(to='locations.SQLLocation', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='supplypointstatus',
            name='status_type',
            field=models.CharField(max_length=50, choices=[(b'rr_fac', b'rr_fac'), (b'trans_fac', b'trans_fac'), (b'soh_fac', b'soh_fac'), (b'super_fac', b'super_fac'), (b'rr_dist', b'rr_dist'), (b'del_del', b'del_del'), (b'la_fac', b'la_fac'), (b'del_dist', b'del_dist'), (b'del_fac', b'del_fac')]),
            preserve_default=True,
        ),
    ]
