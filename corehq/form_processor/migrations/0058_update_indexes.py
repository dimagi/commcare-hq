# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0057_ledger_value_domain_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='commcarecasesql',
            name='server_modified_on',
            field=models.DateTimeField(db_index=True),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='commcarecasesql',
            index_together=set([('domain', 'owner_id', 'closed'), ('domain', 'external_id', 'type')]),
        ),
    ]
