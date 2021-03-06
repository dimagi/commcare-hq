# Generated by Django 1.11.20 on 2019-04-01 10:52

from django.db import migrations, models


INDEX_NAME = 'form_proces_xmlns_8d851e_idx'


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('form_processor', '0078_blobmeta_migrated_check'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} (xmlns)".format(
                INDEX_NAME, 'form_processor_xforminstancesql'
            ),
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS {}".format(INDEX_NAME),
            state_operations=[
                migrations.AddIndex(
                    model_name='xforminstancesql',
                    index=models.Index(fields=['xmlns'], name=INDEX_NAME),
                ),
            ]
        ),
    ]
