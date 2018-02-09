# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def confirm_no_data_loss(apps, schema_editor):
    if apps.get_model('smsbillables', 'SmsBillable').objects.filter(api_response__isnull=False).exists():
        raise Exception(
            'There exists an SmsBillable with api_response != None.'
            ' Preventing this migration because data would be lost.'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0005_update_http_backend_criteria'),
    ]

    operations = [
        HqRunPython(confirm_no_data_loss),
        migrations.RemoveField(
            model_name='smsbillable',
            name='api_response',
        ),
    ]
