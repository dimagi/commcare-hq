# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0003_auto_20151104_2226'),
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
            name='is_archived',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='is_deprecated',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='is_duplicate',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='is_error',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='is_submission_error_log',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
