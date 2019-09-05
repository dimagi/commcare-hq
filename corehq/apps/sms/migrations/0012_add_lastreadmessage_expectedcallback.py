from django.db import migrations, models

import dimagi.utils.couch.migration


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0011_alter_inbound_api_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpectedCallback',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('domain', models.CharField(max_length=126, null=True, db_index=True)),
                ('date', models.DateTimeField(null=True)),
                ('couch_recipient_doc_type', models.CharField(max_length=126, null=True)),
                ('couch_recipient', models.CharField(max_length=126, null=True, db_index=True)),
                ('status', models.CharField(max_length=126, null=True)),
            ],
            options={
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
        migrations.CreateModel(
            name='SQLLastReadMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('domain', models.CharField(max_length=126, null=True)),
                ('read_by', models.CharField(max_length=126, null=True)),
                ('contact_id', models.CharField(max_length=126, null=True)),
                ('message_id', models.CharField(max_length=126, null=True)),
                ('message_timestamp', models.DateTimeField(null=True)),
            ],
            options={
                'db_table': 'sms_lastreadmessage',
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
        migrations.AlterIndexTogether(
            name='sqllastreadmessage',
            index_together=set([('domain', 'contact_id'), ('domain', 'read_by', 'contact_id')]),
        ),
        migrations.AlterIndexTogether(
            name='expectedcallback',
            index_together=set([('domain', 'date')]),
        ),
    ]
