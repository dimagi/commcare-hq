# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0010_merge'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='caseuploadcaserecord',
            name='form_record',
        ),
        migrations.AlterField(
            model_name='caseuploadformrecord',
            name='case_upload_record',
            field=models.ForeignKey(related_name='form_records', to='case_importer.CaseUploadRecord'),
        ),
        migrations.DeleteModel(
            name='CaseUploadCaseRecord',
        ),
    ]
