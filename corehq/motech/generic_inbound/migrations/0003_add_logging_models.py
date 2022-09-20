import uuid

import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('generic_inbound', '0002_configurableapivalidation'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequestLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('status', models.CharField(choices=[('filtered', 'Filtered'), ('validation_failed', 'Validation Failed'), ('success', 'Success'), ('error', 'Error'), ('reverted', 'Reverted')], db_index=True, max_length=32)),
                ('timestamp', models.DateTimeField(auto_now=True, db_index=True)),
                ('attempts', models.PositiveSmallIntegerField(default=1)),
                ('response_status', models.PositiveSmallIntegerField(db_index=True)),
                ('error_message', models.TextField()),
                ('username', models.CharField(db_index=True, max_length=128)),
                ('request_method', models.CharField(choices=[('POST', 'Post'), ('PUT', 'Put'), ('PATCH', 'Patch')], max_length=32)),
                ('request_query', models.CharField(max_length=8192)),
                ('request_body', models.TextField()),
                ('request_headers', models.JSONField(default=dict)),
                ('request_ip', models.GenericIPAddressField(db_index=True)),
                ('api', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='generic_inbound.configurableapi')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProcessingAttempt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now=True, db_index=True)),
                ('is_retry', models.BooleanField(default=False)),
                ('response_status', models.PositiveSmallIntegerField(db_index=True)),
                ('response_body', models.TextField()),
                ('raw_response', models.JSONField(default=dict)),
                ('xform_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('case_ids', django.contrib.postgres.fields.ArrayField(base_field=models.UUIDField(default=uuid.uuid4), blank=True, null=True, size=None)),
                ('log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='generic_inbound.requestlog')),
            ],
        ),
    ]
