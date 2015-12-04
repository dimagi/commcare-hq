# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
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
        (b'form_processor', '0042_noop_change_choice_values'),
        (b'form_processor', '0043_rename_to_match'),
    ]

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='XFormInstanceSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(unique=True, max_length=255, db_index=True)),
                ('domain', models.CharField(max_length=255)),
                ('app_id', models.CharField(max_length=255, null=True)),
                ('xmlns', models.CharField(max_length=255)),
                ('received_on', models.DateTimeField()),
                ('partial_submission', models.BooleanField(default=False)),
                ('submit_ip', models.CharField(max_length=255, null=True)),
                ('last_sync_token', models.CharField(max_length=255, null=True)),
                ('date_header', models.DateTimeField(null=True)),
                ('build_id', models.CharField(max_length=255, null=True)),
                ('state', models.PositiveSmallIntegerField(default=0, choices=[(0, b'normal'), (1, b'archived'), (2, b'deprecated'), (4, b'duplicate'), (8, b'error'), (16, b'submission_error')])),
                ('auth_context', json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object')),
                ('openrosa_headers', json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object')),
                ('deprecated_form_id', models.CharField(max_length=255, null=True)),
                ('edited_on', models.DateTimeField(null=True)),
                ('orig_id', models.CharField(max_length=255, null=True)),
                ('problem', models.TextField(null=True)),
                ('user_id', models.CharField(max_length=255, null=True)),
                ('initial_processing_complete', models.BooleanField(default=False)),
            ],
            options={
            },
            bases=(models.Model, corehq.form_processor.abstract_models.AbstractXFormInstance, dimagi.utils.couch.RedisLockableMixIn),
        ),
        migrations.AlterModelTable(
            name='xforminstancesql',
            table='form_processor_xforminstancesql',
        ),
        migrations.CreateModel(
            name='XFormAttachmentSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment_id', uuidfield.fields.UUIDField(unique=True, max_length=32, db_index=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('content_type', models.CharField(max_length=255)),
                ('md5', models.CharField(max_length=255)),
                ('form', models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'form_id', to='form_processor.XFormInstanceSQL')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelTable(
            name='xformattachmentsql',
            table='form_processor_xformattachmentsql',
        ),
        migrations.CreateModel(
            name='CommCareCaseSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('case_id', models.CharField(unique=True, max_length=255, db_index=True)),
                ('domain', models.CharField(max_length=255)),
                ('type', models.CharField(max_length=255)),
                ('owner_id', models.CharField(max_length=255)),
                ('opened_on', models.DateTimeField(null=True)),
                ('opened_by', models.CharField(max_length=255, null=True)),
                ('modified_on', models.DateTimeField()),
                ('server_modified_on', models.DateTimeField()),
                ('modified_by', models.CharField(max_length=255)),
                ('closed', models.BooleanField(default=False)),
                ('closed_on', models.DateTimeField(null=True)),
                ('closed_by', models.CharField(max_length=255, null=True)),
                ('deleted', models.BooleanField(default=False)),
                ('external_id', models.CharField(max_length=255)),
                ('case_json', json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object')),
                ('name', models.CharField(max_length=255, null=True)),
                ('location_id', models.CharField(max_length=255, null=True)),
            ],
            options={
            },
            bases=(models.Model, corehq.form_processor.abstract_models.AbstractCommCareCase),
        ),
        migrations.AlterIndexTogether(
            name='commcarecasesql',
            index_together=set([('domain', 'owner_id'), ('domain', 'closed', 'server_modified_on')]),
        ),
        migrations.AlterModelTable(
            name='commcarecasesql',
            table='form_processor_commcarecasesql',
        ),
        migrations.CreateModel(
            name='CommCareCaseIndexSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=255)),
                ('identifier', models.CharField(max_length=255)),
                ('referenced_id', models.CharField(max_length=255)),
                ('referenced_type', models.CharField(max_length=255)),
                ('relationship_id', models.PositiveSmallIntegerField(choices=[(0, b'child'), (1, b'extension')])),
                ('case', models.ForeignKey(related_query_name=b'index', related_name='index_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterIndexTogether(
            name='commcarecaseindexsql',
            index_together=set([('domain', 'referenced_id')]),
        ),
        migrations.AlterModelTable(
            name='commcarecaseindexsql',
            table='form_processor_commcarecaseindexsql',
        ),
        migrations.CreateModel(
            name='XFormOperationSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_id', models.CharField(max_length=255, null=True)),
                ('operation', models.CharField(max_length=255)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('form', models.ForeignKey(to='form_processor.XFormInstanceSQL', to_field=b'form_id')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelTable(
            name='xformoperationsql',
            table='form_processor_xformoperationsql',
        ),
        migrations.CreateModel(
            name='CaseAttachmentSQL',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('attachment_id', uuidfield.fields.UUIDField(unique=True, max_length=32, db_index=True)),
                ('name', models.CharField(max_length=255, db_index=True)),
                ('content_type', models.CharField(max_length=255)),
                ('md5', models.CharField(max_length=255)),
                ('case', models.ForeignKey(related_query_name=b'attachment', related_name='attachment_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelTable(
            name='caseattachmentsql',
            table='form_processor_caseattachmentsql',
        ),
        migrations.CreateModel(
            name='CaseTransaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('form_id', models.CharField(max_length=255, null=True)),
                ('server_date', models.DateTimeField()),
                ('type', models.PositiveSmallIntegerField(choices=[(0, b'form'), (1, b'rebuild_with_reason'), (2, b'user_requested_rebuild'), (4, b'user_archived_rebuild'), (8, b'form_archive_rebuild'), (16, b'form_edit_rebuild'), (32, b'ledger')])),
                ('case', models.ForeignKey(related_query_name=b'transaction', related_name='transaction_set', to_field=b'case_id', to='form_processor.CommCareCaseSQL', db_index=True)),
                ('revoked', models.BooleanField(default=False)),
                ('details', json_field.fields.JSONField(default=dict, help_text='Enter a valid JSON object')),
            ],
            options={
                'ordering': ['server_date'],
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='casetransaction',
            unique_together=set([('case', 'form_id')]),
        ),
        migrations.AlterModelTable(
            name='casetransaction',
            table='form_processor_casetransaction',
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX form_processor_commcarecasesql_supply_point_location
                ON form_processor_commcarecasesql(domain, location_id) WHERE type = 'supply-point'
            """,
            reverse_sql='DROP INDEX form_processor_commcarecasesql_supply_point_location',
            state_operations=None,
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
            options=None,
            bases=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_caseattachmentsql_case_id_2a52028042cc318d_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_caseattachmentsql_name_1d9638e12751b7c9_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xforminstancesql_form_id_60f7da828e471288_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformattachmentsql_form_id_2c7940ea539d6de4_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformattachmentsql_name_4b9f1b0d840a70bc_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_xformoperationsql_form_id_6610a535ea713665_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_commcarecaseindexs_case_id_7db75a61e418ebfc_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_commcarecasesql_case_id_3dee99b8828d1543_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
        migrations.RunSQL(
            sql='DROP INDEX IF EXISTS form_processor_casetransaction_case_id_6c13626ba79fe02e_like',
            reverse_sql='SELECT 1',
            state_operations=None,
        ),
    ]
