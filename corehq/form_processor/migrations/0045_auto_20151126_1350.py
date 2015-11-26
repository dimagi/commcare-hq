# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0044_auto_20151126_1348'),
    ]

    operations = [
        migrations.RenameField(
            model_name='caseattachmentsql',
            old_name='attachment_uuid',
            new_name='attachment_id',
        ),
        migrations.RenameField(
            model_name='xformattachmentsql',
            old_name='attachment_uuid',
            new_name='attachment_id',
        ),
    ]
