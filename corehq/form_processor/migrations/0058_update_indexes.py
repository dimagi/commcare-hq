# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('form_processor', '0057_ledger_value_domain_location'),
    ]

    operations = [
        # case
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

        # case attachment
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='name',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='caseattachmentsql',
            index_together=set([('case', 'identifier')]),
        ),

        # form attachment
        migrations.AlterIndexTogether(
            name='xformattachmentsql',
            index_together=set([('form', 'name')]),
        ),

        # case index
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_id',
                                    to='form_processor.CommCareCaseSQL', db_index=False),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='commcarecaseindexsql',
            index_together=set([('domain', 'case'), ('domain', 'referenced_id')]),
        ),

        # case transaction
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(
                related_name="transaction_set", related_query_name=b"transaction", to_field=b'case_id',
                to='form_processor.CommCareCaseSQL', db_index=False),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='casetransaction',
            index_together=set([('case', 'form_id'), ('case', 'server_date', 'sync_log_id')]),
        ),
    ]
