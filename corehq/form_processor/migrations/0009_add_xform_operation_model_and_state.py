# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0008_add_index_for_caseforms_case_uuid'),
    ]

    operations = [
        migrations.CreateModel(
            name='XFormOperationSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user', models.CharField(max_length=255, null=True)),
                ('operation', models.CharField(max_length=255)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('xform', models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_uuid')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (3, b'duplicate'), (4, b'error'), (5, b'submission_error')]),
            preserve_default=True,
        ),
    ]
