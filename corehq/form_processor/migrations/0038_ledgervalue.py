# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0037_get_form_by_id_fn'),
    ]

    operations = [
        migrations.CreateModel(
            name='LedgerValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('product_id', models.CharField(max_length=100, db_index=True)),
                ('section_id', models.CharField(max_length=100, db_index=True)),
                ('balance', models.IntegerField(default=0)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field=b'case_id')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
