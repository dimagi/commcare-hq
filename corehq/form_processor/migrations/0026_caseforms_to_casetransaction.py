# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0025_caseforms_server_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseTransaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_uuid', models.CharField(max_length=255)),
                ('server_date', models.DateTimeField()),
                ('type', models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild')])),
                ('case', models.ForeignKey(related_query_name=b'xform', related_name='xform_set', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False)),
            ],
            options={
                'ordering': ['server_date'],
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='caseforms',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='caseforms',
            name='case',
        ),
        migrations.DeleteModel(
            name='CaseForms',
        ),
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_uuid')]),
        ),
    ]
