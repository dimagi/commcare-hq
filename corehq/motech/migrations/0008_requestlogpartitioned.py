from django.db import migrations, models

import jsonfield.fields
from architect.commands import partition


def add_partitions(apps, schema_editor):
    partition.run({'module': 'corehq.motech.models'})


class Migration(migrations.Migration):

    dependencies = [
        ('motech', '0007_auto_20200909_2138'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequestLogPartitioned',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True,
                                        serialize=False,
                                        verbose_name='ID')),
                ('domain', models.CharField(max_length=126)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('log_level', models.IntegerField(blank=True, null=True)),
                ('payload_id', models.CharField(max_length=32,
                                                blank=True, null=True)),
                ('request_method', models.CharField(max_length=12)),
                ('request_url', models.CharField(max_length=255)),
                ('request_headers', jsonfield.fields.JSONField(blank=True)),
                ('request_params', jsonfield.fields.JSONField(blank=True)),
                ('request_body', models.TextField(blank=True, null=True)),
                ('request_error', models.TextField(blank=True, null=True)),
                ('response_status', models.IntegerField(blank=True, null=True)),
                ('response_headers', jsonfield.fields.JSONField(blank=True)),
                ('response_body', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'motech_requestlog',
            },
        ),
        migrations.AddIndex(
            model_name='requestlogpartitioned',
            index=models.Index(fields=['domain'], name='motech_requ_domain_a28b70_idx'),
        ),
        migrations.AddIndex(
            model_name='requestlogpartitioned',
            index=models.Index(fields=['timestamp'], name='motech_requ_timesta_5aa7ef_idx'),
        ),
        migrations.AddIndex(
            model_name='requestlogpartitioned',
            index=models.Index(fields=['payload_id'], name='motech_requ_payload_5ce888_idx'),
        ),
        migrations.AddIndex(
            model_name='requestlogpartitioned',
            index=models.Index(fields=['request_url'], name='motech_requ_request_31bcb4_idx'),
        ),
        migrations.AddIndex(
            model_name='requestlogpartitioned',
            index=models.Index(fields=['response_status'], name='motech_requ_respons_d371a0_idx'),
        ),
        migrations.RunPython(add_partitions),
    ]
