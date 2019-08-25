# -*- coding: utf-8 -*-

from django.db import models, migrations
import dimagi.utils.couch
import corehq.form_processor.abstract_models


class Migration(migrations.Migration):

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
            options={
            },
            bases=(models.Model, corehq.form_processor.abstract_models.AbstractXFormInstance, dimagi.utils.couch.RedisLockableMixIn),
        ),
    ]
