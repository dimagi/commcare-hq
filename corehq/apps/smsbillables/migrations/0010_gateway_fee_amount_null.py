# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations

from corehq.apps.smsbillables.models import add_twilio_gateway_fee
from corehq.sql_db.operations import HqRunPython


def add_twilio_gateway_fee_for_migration(apps, schema_editor):
    add_twilio_gateway_fee(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('smsbillables', '0009_smsbillable_direct_gateway_fee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='smsgatewayfee',
            name='amount',
            field=models.DecimalField(null=True, max_digits=10, decimal_places=4),
            preserve_default=True,
        ),
        HqRunPython(add_twilio_gateway_fee_for_migration),
    ]
