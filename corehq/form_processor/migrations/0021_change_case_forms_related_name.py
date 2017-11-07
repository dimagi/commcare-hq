# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0020_rename_index_relationship'),
    ]

    operations = [
        migrations.AlterField(
            model_name='caseforms',
            name='case',
            field=models.ForeignKey(related_query_name=b'xform', related_name='xform_set', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
