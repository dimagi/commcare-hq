# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0009_caseuploadrecord_comment'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseUploadFormRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(unique=True, max_length=256)),
                ('case_upload_record', models.ForeignKey(related_name='form_records', to='case_importer.CaseUploadRecord')),
            ],
        ),
    ]
