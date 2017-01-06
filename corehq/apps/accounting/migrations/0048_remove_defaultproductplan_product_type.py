# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def delete_deprecated_default_plans(apps, schema_editor):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    DefaultProductPlan.objects.filter(product_type__in=[
        'CommTrack',
        'CommConnect'
    ]).delete()


def assert_only_commcare_default_plans(apps, schema_editor):
    DefaultProductPlan = apps.get_model('accounting', 'DefaultProductPlan')
    assert not DefaultProductPlan.objects.exclude(product_type='CommCare').exists()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0047_ensure_default_product_plans'),
    ]

    operations = [
        HqRunPython(delete_deprecated_default_plans),
        HqRunPython(assert_only_commcare_default_plans),
        migrations.RemoveField(
            model_name='defaultproductplan',
            name='product_type',
        ),
        migrations.AlterUniqueTogether(
            name='defaultproductplan',
            unique_together=set([('edition', 'is_trial')]),
        ),
    ]
