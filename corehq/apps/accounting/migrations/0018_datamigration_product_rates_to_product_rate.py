# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from corehq.sql_db.operations import HqRunPython


def check_single_product_rates(apps, schema_editor):
    invalid_plan_version_ids = [
        str(plan_version.id)
        for plan_version in apps.get_model('accounting', 'SoftwarePlanVersion').objects.all()
        if plan_version.product_rates.count() != 1
    ]
    if invalid_plan_version_ids:
        raise Exception(
            "len(product_rates) != 1 for the following SoftwarePlanVersion(s): %s"
            % ', '.join(invalid_plan_version_ids)
        )


def copy_product_rates_to_product_rate(apps, schema_editor):
    for plan_version in apps.get_model('accounting', 'SoftwarePlanVersion').objects.all():
        plan_version.product_rate = plan_version.product_rates.all()[0]
        plan_version.save()


def copy_product_rate_to_product_rates(apps, schema_editor):
    for plan_version in apps.get_model('accounting', 'SoftwarePlanVersion').objects.all():
        if plan_version.product_rate:
            plan_version.product_rates = [plan_version.product_rate]
            plan_version.save()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0017_add_product_rate'),
    ]

    operations = [
        HqRunPython(check_single_product_rates, reverse_code=(lambda apps, schema_editor: None)),
        HqRunPython(copy_product_rates_to_product_rate, reverse_code=copy_product_rate_to_product_rates),
    ]
