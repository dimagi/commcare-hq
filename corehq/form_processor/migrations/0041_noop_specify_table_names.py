# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0040_save_functions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='caseattachmentsql',
            table='form_processor_caseattachmentsql',
        ),
        migrations.AlterModelTable(
            name='casetransaction',
            table='form_processor_casetransaction',
        ),
        migrations.AlterModelTable(
            name='commcarecaseindexsql',
            table='form_processor_commcarecaseindexsql',
        ),
        migrations.AlterModelTable(
            name='commcarecasesql',
            table='form_processor_commcarecasesql',
        ),
        migrations.AlterModelTable(
            name='xformattachmentsql',
            table='form_processor_xformattachmentsql',
        ),
        migrations.AlterModelTable(
            name='xforminstancesql',
            table='form_processor_xforminstancesql',
        ),
        migrations.AlterModelTable(
            name='xformoperationsql',
            table='form_processor_xformoperationsql',
        ),
    ]
