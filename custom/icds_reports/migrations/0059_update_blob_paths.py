# Generated by Django 1.11.14 on 2018-08-03 20:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0058_new_agg_ccs_columns'),
    ]

    operations = [
        migrations.RunSQL(
            # This migration is not reversible because blobs created
            # since the migration will no longer be accessible after
            # reversing because the old blob db would use the wrong path
            """
            UPDATE icds_reports_icdsfile
            SET blob_id = 'icds_blobdb/' || blob_id
            WHERE blob_id NOT LIKE 'icds_blobdb/%'
            """
        ),
    ]
