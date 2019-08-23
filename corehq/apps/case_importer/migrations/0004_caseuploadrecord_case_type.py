# -*- coding: utf-8 -*-

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('case_importer', '0003_caseuploadrecord_couch_user_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='caseuploadrecord',
            name='case_type',
            field=models.CharField(default='case', max_length=256),
            preserve_default=False,
        ),
    ]
