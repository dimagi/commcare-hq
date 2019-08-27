
from django.db import migrations, models

import jsonfield.fields

import dimagi.utils.couch.migration


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0020_remove_selfregistrationinvitation_odk_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='Keyword',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('domain', models.CharField(max_length=126, db_index=True)),
                ('keyword', models.CharField(max_length=126)),
                ('description', models.TextField(null=True)),
                ('delimiter', models.CharField(max_length=126, null=True)),
                ('override_open_sessions', models.NullBooleanField()),
                ('initiator_doc_type_filter', jsonfield.fields.JSONField(default=list)),
            ],
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
        migrations.CreateModel(
            name='KeywordAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=126)),
                ('recipient', models.CharField(max_length=126)),
                ('recipient_id', models.CharField(max_length=126, null=True)),
                ('message_content', models.TextField(null=True)),
                ('form_unique_id', models.CharField(max_length=126, null=True)),
                ('use_named_args', models.NullBooleanField()),
                ('named_args', jsonfield.fields.JSONField(default=dict)),
                ('named_args_separator', models.CharField(max_length=126, null=True)),
                ('keyword', models.ForeignKey(to='sms.Keyword', on_delete=models.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='SQLICDSBackend',
            fields=[
            ],
            options={
                'proxy': True,
            },
            bases=('sms.sqlsmsbackend',),
        ),
        migrations.AlterIndexTogether(
            name='keyword',
            index_together=set([('domain', 'keyword')]),
        ),
    ]
