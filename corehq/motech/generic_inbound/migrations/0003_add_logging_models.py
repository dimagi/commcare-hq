import uuid

import django.contrib.postgres.fields
import django.contrib.postgres.indexes
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
                ('domain', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('filtered', 'Filtered'), ('validation_failed', 'Validation Failed'), ('success', 'Success'), ('error', 'Error'), ('reverted', 'Reverted')], max_length=32)),
                ('timestamp', models.DateTimeField(auto_now=True, db_index=True)),
                ('attempts', models.PositiveSmallIntegerField(default=1)),
                ('response_status', models.PositiveSmallIntegerField()),
                ('error_message', models.TextField()),
                ('username', models.CharField(max_length=128)),
                ('request_method', models.CharField(choices=[('POST', 'Post'), ('PUT', 'Put'), ('PATCH', 'Patch')], max_length=32)),
                ('request_query', models.CharField(max_length=8192)),
                ('request_body', models.TextField()),
                ('request_headers', models.JSONField(default=dict)),
                ('request_ip', models.GenericIPAddressField()),
                ('api', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='generic_inbound.configurableapi')),
            ],
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
                ('xform_id', models.CharField(blank=True, db_index=True, max_length=36, null=True)),
                ('case_ids', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=36), blank=True, null=True, size=None)),
                ('log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='generic_inbound.requestlog')),
            ],
        ),
        migrations.AddIndex(
            model_name='requestlog',
            index=models.Index(fields=['domain'], name='generic_inb_domain_7c4747_idx'),
        ),
        migrations.AddIndex(
            model_name='requestlog',
            index=models.Index(fields=['status'], name='generic_inb_status_82f197_idx'),
        ),
        migrations.AddIndex(
            model_name='requestlog',
            index=models.Index(fields=['username'], name='generic_inb_usernam_cfab8d_idx'),
        ),
    ]
