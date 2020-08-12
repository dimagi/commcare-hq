# -*- coding: utf-8 -*-
# Generated on 2020-03-21
from __future__ import unicode_literals
from django.db import migrations
from custom.icds_reports.utils.migrations import get_view_migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0171_add_sdr_field_and_view'),
    ]

    operations = [
        migrations.RunSQL('ALTER TABLE awc_location ADD COLUMN awc_ward_1 text'),
        migrations.RunSQL('ALTER TABLE awc_location ADD COLUMN awc_ward_2 text'),
        migrations.RunSQL('ALTER TABLE awc_location ADD COLUMN awc_ward_3 text'),
        migrations.RunSQL('ALTER TABLE awc_location_local ADD COLUMN awc_ward_1 text'),
        migrations.RunSQL('ALTER TABLE awc_location_local ADD COLUMN awc_ward_2 text'),
        migrations.RunSQL('ALTER TABLE awc_location_local ADD COLUMN awc_ward_3 text'),
    ]
