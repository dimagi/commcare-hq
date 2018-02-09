# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import models, migrations
import dimagi.utils.couch.migration


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0015_rename_phonenumber_to_phoneblacklist'),
    ]

    operations = [
        migrations.CreateModel(
            name='PhoneNumber',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('couch_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('domain', models.CharField(max_length=126, null=True, db_index=True)),
                ('owner_doc_type', models.CharField(max_length=126, null=True)),
                ('owner_id', models.CharField(max_length=126, null=True, db_index=True)),
                ('phone_number', models.CharField(max_length=126, null=True, db_index=True)),
                ('backend_id', models.CharField(max_length=126, null=True)),
                ('ivr_backend_id', models.CharField(max_length=126, null=True)),
                ('verified', models.NullBooleanField(default=False)),
                ('contact_last_modified', models.DateTimeField(null=True)),
            ],
            options={
            },
            bases=(dimagi.utils.couch.migration.SyncSQLToCouchMixin, models.Model),
        ),
    ]
