# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from corehq.sql_db.operations import HqRunPython


def check_no_credit_lines_feature_type_any(apps, schema_editor):
    if apps.get_model('accounting', 'CreditLine').objects.filter(feature_type='').exists():
        raise Exception(
            "There exists a credit line with feature type 'Any'.\n"
            "Execute CreditLine.objects.filter(feature_type="").delete() to proceed."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0012_billing_metadata_data_migration'),
    ]

    operations = [
        HqRunPython(check_no_credit_lines_feature_type_any),
        migrations.AlterField(
            model_name='creditline',
            name='feature_type',
            field=models.CharField(max_length=10, null=True, choices=[(b'User', b'User'), (b'SMS', b'SMS')]),
            preserve_default=True,
        ),
    ]
