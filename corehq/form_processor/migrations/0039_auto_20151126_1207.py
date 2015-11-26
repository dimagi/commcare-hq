# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0038_auto_20151126_1206'),
    ]

    operations = [
        migrations.RenameField(
            model_name='casetransaction',
            old_name='form_uuid',
            new_name='form_id',
        ),
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_id')]),
        ),
    ]
