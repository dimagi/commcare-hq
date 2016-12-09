# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0006_caseuploadrecord_upload_file_meta'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseUploadCaseRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('case_id', models.CharField(max_length=256)),
            ],
        ),
        migrations.CreateModel(
            name='CaseUploadFormRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(unique=True, max_length=256)),
                ('case_upload_record', models.ForeignKey(to='case_importer.CaseUploadRecord')),
            ],
        ),
        migrations.AddField(
            model_name='caseuploadcaserecord',
            name='form_record',
            field=models.ForeignKey(to='case_importer.CaseUploadFormRecord'),
        ),
    ]
