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
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set',
                                    to_field='case_id', to='form_processor.CommCareCaseSQL', db_index=False,
                                    on_delete=models.CASCADE),
            preserve_default=True,
        ),
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
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='form',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set',
                                    to_field='form_id', to='form_processor.XFormInstanceSQL', db_index=False,
                                    on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='name',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='xformattachmentsql',
            index_together=set([('form', 'name')]),
        ),

        # case index
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field='case_id',
                                    to='form_processor.CommCareCaseSQL', db_index=False,
                                    on_delete=models.CASCADE),
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
                related_name="transaction_set", related_query_name=b"transaction", to_field='case_id',
                to='form_processor.CommCareCaseSQL', db_index=False, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='casetransaction',
            index_together=set([('case', 'server_date', 'sync_log_id')]),
        ),

        # ledger transaction
        migrations.AlterField(
            model_name='ledgertransaction',
            name='case_id',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='ledgertransaction',
            index_together=set([('case_id', 'section_id', 'entry_id')]),
        ),

        # ledger value
        migrations.AlterField(
            model_name='ledgervalue',
            name='case_id',
            field=models.CharField(default=None, max_length=255),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='entry_id',
            field=models.CharField(default=None, max_length=100),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='last_modified',
            field=models.DateTimeField(auto_now=True, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='ledgervalue',
            name='section_id',
            field=models.CharField(default=None, max_length=100),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='ledgervalue',
            unique_together=set([('case_id', 'section_id', 'entry_id')]),
        ),

        # form
        migrations.AlterField(
            model_name='xforminstancesql',
            name='received_on',
            field=models.DateTimeField(db_index=True),
            preserve_default=True,
        ),
        migrations.AlterIndexTogether(
            name='xforminstancesql',
            index_together=set([('domain', 'user_id'), ('domain', 'state')]),
        ),
    ]
