# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
import dimagi.utils.couch
import uuidfield.fields
import json_field.fields
import corehq.form_processor.abstract_models


class Migration(migrations.Migration):

    replaces = [
        (b'form_processor', '0001_initial'),
        (b'form_processor', '0002_xformattachmentsql'),
        (b'form_processor', '0003_auto_20151104_2226'),
        (b'form_processor', '0004_create_commcarecasesql'),
        (b'form_processor', '0005_make_case_uuid_unique_indexed'),
        (b'form_processor', '0006_commcarecaseindexsql'),
        (b'form_processor', '0007_index_case_uuid_on_commcarecaseindex'),
        (b'form_processor', '0008_add_index_for_caseforms_case_uuid'),
        (b'form_processor', '0009_add_xform_operation_model_and_state'),
        (b'form_processor', '0010_add_auth_and_openrosa_fields'),
        (b'form_processor', '0011_add_fields_for_deprecation'),
        (b'form_processor', '0012_xforminstancesql_problem'),
        (b'form_processor', '0013_caseattachmentsql'),
        (b'form_processor', '0014_caseattachmentsql_index_on_foreign_key'),
        (b'form_processor', '0015_change_related_names_for_form_attachment'),
        (b'form_processor', '0016_index_case_attachment_uuid'),
        (b'form_processor', '0017_problem_to_text_field'),
        (b'form_processor', '0018_xforminstancesql_user_id'),
        (b'form_processor', '0019_allow_closed_by_null'),
        (b'form_processor', '0020_rename_index_relationship'),
        (b'form_processor', '0021_change_case_forms_related_name'),
        (b'form_processor', '0022_set_default_value_for_case_json'),
        (b'form_processor', '0023_make_case_name_top_level'),
        (b'form_processor', '0024_rename_case_type'),
        (b'form_processor', '0025_caseforms_server_date'),
        (b'form_processor', '0026_caseforms_to_casetransaction'),
        (b'form_processor', '0027_allow_null_form_uuid_in_case_transaction'),
        (b'form_processor', '0025_add_dict_defaults_for_xform'),
        (b'form_processor', '0026_xforminstancesql_initial_processing_complete'),
        (b'form_processor', '0028_merge'),
        (b'form_processor', '0029_drop_not_null_from_opened_on_by'),
        (b'form_processor', '0030_casetransaction_revoked'),
        (b'form_processor', '0031_add_details_field_to_case_transaction'),
        (b'form_processor', '0032_change_transaction_related_name'),
        (b'form_processor', '0033_commcarecasesql_location_uuid'),
        (b'form_processor', '0034_location_id_index'),
        (b'form_processor', '0035_remove_varchar_pattern_ops_indexes'),
        (b'form_processor', '0036_cleanup_models'),
        (b'form_processor', '0037_get_form_by_id_fn'),
        (b'form_processor', '0038_form_functions'),
        (b'form_processor', '0039_auto_20151130_1748'),
        (b'form_processor', '0039_case_functions'),
        (b'form_processor', '0040_save_functions'),
        (b'form_processor', '0041_noop_specify_table_names'),
        (b'form_processor', '0042_noop_change_choice_values')
    ]

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='XFormInstanceSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_uuid', models.CharField(unique=True, max_length=255, db_index=True)),
                ('domain', models.CharField(max_length=255)),
                ('app_id', models.CharField(max_length=255, null=True)),
                ('xmlns', models.CharField(max_length=255)),
                ('received_on', models.DateTimeField()),
                ('partial_submission', models.BooleanField(default=False)),
                ('submit_ip', models.CharField(max_length=255, null=True)),
                ('last_sync_token', models.CharField(max_length=255, null=True)),
                ('date_header', models.DateTimeField(null=True)),
                ('build_id', models.CharField(max_length=255, null=True)),
            ],
            bases=(models.Model, corehq.form_processor.abstract_models.AbstractXFormInstance, dimagi.utils.couch.RedisLockableMixIn),
        ),
        migrations.AlterModelTable(
            name='xforminstancesql',
            table='form_processor_xforminstancesql',
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (3, b'duplicate'), (4, b'error'), (5, b'submission_error')]),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='auth_context',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='openrosa_headers',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='deprecated_form_id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='edited_on',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='orig_id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='problem',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='user_id',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='xforminstancesql',
            name='initial_processing_complete',
            field=models.BooleanField(default=False),
        ),
        migrations.RenameField(
            model_name='xforminstancesql',
            old_name='form_uuid',
            new_name='form_id',
        ),
        migrations.AlterField(
            model_name='xforminstancesql',
            name='state',
            field=models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (4, b'duplicate'), (8, b'error'), (16, b'submission_error')]),
        ),



        
        migrations.CreateModel(
            name='XFormAttachmentSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment_uuid', models.CharField(unique=True, max_length=255, db_index=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('content_type', models.CharField(max_length=255)),
                ('md5', models.CharField(max_length=255)),
                ('xform', models.ForeignKey(related_query_name=b'attachment', related_name='attachments', db_column=b'form_uuid', to_field=b'form_uuid', to='form_processor.XFormInstanceSQL')),
            ],
        ),
        migrations.AlterModelTable(
            name='xformattachmentsql',
            table='form_processor_xformattachmentsql',
        ),
        migrations.RenameField(
            model_name='xformattachmentsql',
            old_name='xform',
            new_name='form',
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='form',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'form_uuid', to='form_processor.XFormInstanceSQL'),
        ),
        migrations.RenameField(
            model_name='xformoperationsql',
            old_name='xform',
            new_name='form',
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='form',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='form',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'form_id', to='form_processor.XFormInstanceSQL'),
        ),
        migrations.AlterField(
            model_name='xformattachmentsql',
            name='form',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'form_id', to='form_processor.XFormInstanceSQL'),
        ),
        migrations.RenameField(
            model_name='xformattachmentsql',
            old_name='attachment_uuid',
            new_name='attachment_id',
        ),

        migrations.RunSQL(
            sql='ALTER TABLE "form_processor_xformattachmentsql" ALTER COLUMN "attachment_id" TYPE uuid USING attachment_id::uuid',
            reverse_sql='ALTER TABLE "form_processor_xformattachmentsql" ALTER COLUMN "attachment_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='xformattachmentsql',
                name='attachment_id',
                field=uuidfield.fields.UUIDField(unique=True, max_length=32, db_index=True),
            )],
        ),
        migrations.CreateModel(
            name='CommCareCaseSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('case_uuid', models.CharField(max_length=255)),
                ('domain', models.CharField(max_length=255)),
                ('case_type', models.CharField(max_length=255)),
                ('owner_id', models.CharField(max_length=255)),
                ('opened_on', models.DateTimeField()),
                ('opened_by', models.CharField(max_length=255)),
                ('modified_on', models.DateTimeField()),
                ('server_modified_on', models.DateTimeField()),
                ('modified_by', models.CharField(max_length=255)),
                ('closed', models.BooleanField(default=False)),
                ('closed_on', models.DateTimeField(null=True)),
                ('closed_by', models.CharField(max_length=255)),
                ('deleted', models.BooleanField(default=False)),
                ('external_id', models.CharField(max_length=255)),
                ('case_json', json_field.fields.JSONField(default='null', help_text='Enter a valid JSON object')),
                ('attachments_json', json_field.fields.JSONField(default='null', help_text='Enter a valid JSON object')),
            ],
            bases=(models.Model, corehq.form_processor.abstract_models.AbstractCommCareCase),
        ),
        migrations.AlterModelTable(
            name='commcarecasesql',
            table='form_processor_commcarecasesql',
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='case_uuid',
            field=models.CharField(unique=True, max_length=255, db_index=True),
        ),
        migrations.RemoveField(
            model_name='commcarecasesql',
            name='attachments_json',
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='closed_by',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='case_json',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
        ),
        migrations.AddField(
            model_name='commcarecasesql',
            name='name',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='case_type',
            new_name='type',
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='opened_by',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='commcarecasesql',
            name='opened_on',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='commcarecasesql',
            name='location_uuid',
            field=uuidfield.fields.UUIDField(max_length=32, null=True),
        ),
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='location_uuid',
            new_name='location_id',
        ),
        migrations.RenameField(
            model_name='commcarecasesql',
            old_name='case_uuid',
            new_name='case_id',
        ),
        migrations.AlterIndexTogether(
            name='commcarecasesql',
            index_together=set([('domain', 'owner_id'), ('domain', 'closed', 'server_modified_on')]),
        ),
        migrations.RunSQL(
            sql='ALTER TABLE form_processor_commcarecasesql ALTER COLUMN "location_id" TYPE varchar(255)',
            reverse_sql='ALTER TABLE form_processor_commcarecasesql ALTER COLUMN "location_id" TYPE uuid USING location_id::uuid',
            state_operations=[migrations.AlterField(
                model_name='commcarecasesql',
                name='location_id',
                field=models.CharField(max_length=255, null=True),
            )],
        ),


        migrations.CreateModel(
            name='CommCareCaseIndexSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255)),
                ('identifier', models.CharField(max_length=255)),
                ('referenced_id', models.CharField(max_length=255)),
                ('referenced_type', models.CharField(max_length=255)),
                ('relationship', models.PositiveSmallIntegerField(choices=[(0, b'child'), (1, b'extension')])),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field=b'case_uuid', db_column=b'case_uuid', db_index=False)),
            ],
        ),
        migrations.AlterModelTable(
            name='commcarecaseindexsql',
            table='form_processor_commcarecaseindexsql',
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(to='form_processor.CommCareCaseSQL', db_column=b'case_uuid', to_field=b'case_uuid'),
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL'),
        ),
        migrations.RenameField(
            model_name='commcarecaseindexsql',
            old_name='relationship',
            new_name='relationship_id',
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL'),
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='commcarecaseindexsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
        ),
        migrations.AlterIndexTogether(
            name='commcarecaseindexsql',
            index_together=set([('domain', 'referenced_id')]),
        ),



        migrations.CreateModel(
            name='CaseForms',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_uuid', models.CharField(max_length=255)),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field=b'case_uuid', db_column=b'case_uuid', db_index=False)),
            ],
        ),
        migrations.AlterField(
            model_name='caseforms',
            name='case',
            field=models.ForeignKey(related_query_name=b'xform', related_name='xform_set', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False),
        ),
        migrations.AddField(
            model_name='caseforms',
            name='server_date',
            field=models.DateTimeField(default=datetime.datetime(2015, 11, 13, 9, 21, 40, 422766)),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='caseforms',
            unique_together=set([('case', 'form_uuid')]),
        ),
        migrations.AlterUniqueTogether(
            name='caseforms',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='caseforms',
            name='case',
        ),
        migrations.DeleteModel(
            name='CaseForms',
        ),
        migrations.CreateModel(
            name='XFormOperationSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user', models.CharField(max_length=255, null=True)),
                ('operation', models.CharField(max_length=255)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('xform', models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_uuid')),
            ],
        ),
        migrations.AlterModelTable(
            name='xformoperationsql',
            table='form_processor_xformoperationsql',
        ),
        migrations.AlterField(
            model_name='xformoperationsql',
            name='form',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='xformoperationsql',
            name='form',
            field=models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_id'),
        ),
        migrations.RenameField(
            model_name='xformoperationsql',
            old_name='user',
            new_name='user_id',
        ),


        migrations.CreateModel(
            name='CaseAttachmentSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment_uuid', models.CharField(unique=True, max_length=255, db_index=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('content_type', models.CharField(max_length=255)),
                ('md5', models.CharField(max_length=255)),
                ('case', models.ForeignKey(related_query_name=b'attachment', related_name='attachments', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AlterModelTable(
            name='caseattachmentsql',
            table='form_processor_caseattachmentsql',
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL'),
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachments', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
        ),
        migrations.AlterField(
            model_name='caseattachmentsql',
            name='case',
            field=models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
        ),
        migrations.RenameField(
            model_name='caseattachmentsql',
            old_name='attachment_uuid',
            new_name='attachment_id',
        ),
        migrations.RunSQL(
            sql='ALTER TABLE "form_processor_caseattachmentsql" ALTER COLUMN "attachment_id" TYPE uuid USING attachment_id::uuid',
            reverse_sql='ALTER TABLE "form_processor_caseattachmentsql" ALTER COLUMN "attachment_id" TYPE varchar(255)',
            state_operations=[migrations.AlterField(
                model_name='caseattachmentsql',
                name='attachment_id',
                field=uuidfield.fields.UUIDField(unique=True, max_length=32, db_index=True),
            )],
        ),





        migrations.CreateModel(
            name='CaseTransaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_uuid', models.CharField(max_length=255)),
                ('server_date', models.DateTimeField()),
                ('type', models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild')])),
                ('case', models.ForeignKey(related_query_name=b'xform', related_name='xform_set', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False)),
            ],
            options={
                'ordering': ['server_date'],
            },
        ),
        migrations.AlterModelTable(
            name='casetransaction',
            table='form_processor_casetransaction',
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='form_uuid',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='casetransaction',
            name='revoked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='casetransaction',
            name='details',
            field=json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object'),
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (3, b'user_archived_rebuild'), (4, b'form_archive_rebuild'), (5, b'form_edit_rebuild')]),
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', db_column=b'case_uuid', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False),
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_uuid', to='form_processor.CommCareCaseSQL', db_index=False),
        ),
        migrations.RenameField(
            model_name='casetransaction',
            old_name='form_uuid',
            new_name='form_id',
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.CharField(max_length=255),
        ),

        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL'),
        ),

        migrations.AlterField(
            model_name='casetransaction',
            name='case',
            field=models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL', db_index=False),
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (3, b'user_archived_rebuild'), (4, b'form_archive_rebuild'), (5, b'form_edit_rebuild'), (6, b'ledger')]),
        ),
        migrations.AlterField(
            model_name='casetransaction',
            name='type',
            field=models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (4, b'user_archived_rebuild'), (8, b'form_archive_rebuild'), (16, b'form_edit_rebuild'), (32, b'ledger')]),
        ),
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_id')]),
        ),

        migrations.RunSQL(
            sql="\n                CREATE INDEX form_processor_commcarecasesql_supply_point_location\n                ON form_processor_commcarecasesql(domain, location_uuid) WHERE type = 'supply-point'\n            ",
            reverse_sql='\n                DROP INDEX form_processor_commcarecasesql_supply_point_location\n            ',
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xforminstancesql_form_uuid_12662b9ceadeeecc_like',
            reverse_sql='SELECT 1',
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformattac_attachment_uuid_6d1d0a1eff4ada21_like',
            reverse_sql='SELECT 1',
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformattachmentsql_name_4b9f1b0d840a70bc_like',
            reverse_sql='SELECT 1',
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformoperationsql_xform_id_14e64e95f71c3764_like',
            reverse_sql='SELECT 1',
        ),

















        migrations.CreateModel(
            name='LedgerValue',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('entry_id', models.CharField(max_length=100, db_index=True)),
                ('section_id', models.CharField(max_length=100, db_index=True)),
                ('balance', models.IntegerField(default=0)),
                ('last_modified', models.DateTimeField(auto_now=True)),
                ('case', models.ForeignKey(to='form_processor.CommCareCaseSQL', to_field=b'case_id')),
            ],
        ),








    ]
