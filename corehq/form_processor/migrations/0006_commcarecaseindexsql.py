# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0005_make_case_uuid_unique_indexed'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommCareCaseIndexSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255)),
                ('identifier', models.CharField(max_length=255)),
                ('referenced_id', models.CharField(max_length=255)),
                ('referenced_type', models.CharField(max_length=255)),
                ('relationship', models.PositiveSmallIntegerField(choices=[(0, b'child'), (1, b'extension')])),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field=b'case_uuid', db_column=b'case_uuid', db_index=False)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterIndexTogether(
            name='commcarecaseindexsql',
            index_together=set([('domain', 'referenced_id')]),
        ),
    ]
