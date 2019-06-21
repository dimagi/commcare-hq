# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations




def delete_old_ucr_pillow_errors(apps, schema_editor):
    PillowError = apps.get_model("pillow_retry", "PillowError")
    deleted_names = (
        'corehq.apps.userreports.pillow.StaticDataSourcePillow',
        'corehq.apps.userreports.pillow.ConfigurableIndicatorPillow',
    )
    for name in deleted_names:
        PillowError.objects.filter(pillow=name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pillow_retry', '0003_auto_20151002_0944'),
    ]

    operations = [
        migrations.RunPython(delete_old_ucr_pillow_errors)
    ]
