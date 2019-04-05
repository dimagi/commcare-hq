# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, IntegrityError




def rename_static_data_source_pillow_errors(apps, schema_editor):
    PillowError = apps.get_model("pillow_retry", "PillowError")
    old_name = 'corehq.apps.userreports.pillow.CustomDataSourcePillow'
    new_name = 'corehq.apps.userreports.pillow.StaticDataSourcePillow'
    for error_record in PillowError.objects.filter(pillow=old_name):
        try:
            error_record.pillow = new_name
            error_record.save()
        except IntegrityError:
            error_record.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pillow_retry', '0002_pillowerror_queued'),
    ]

    operations = [
        migrations.RunPython(rename_static_data_source_pillow_errors)
    ]
