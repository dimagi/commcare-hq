# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ilsgateway', '0007_auto_20160322_1434'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='historicallocationgroup',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='historicallocationgroup',
            name='location_id',
        ),
        migrations.DeleteModel(
            name='HistoricalLocationGroup',
        ),
        migrations.DeleteModel(
            name='ILSGatewayWebUser',
        ),
        migrations.DeleteModel(
            name='ILSMigrationProblem',
        ),
        migrations.DeleteModel(
            name='ILSMigrationStats',
        )
    ]
