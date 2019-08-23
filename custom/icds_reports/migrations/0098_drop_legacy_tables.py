# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations
from django.db.migrations import RunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0097_awwincentivereport_district_id'),
    ]

    operations = [
        RunSQL('DROP TABLE IF EXISTS agg_thr_data CASCADE'),
        RunSQL('DROP TABLE IF EXISTS ccs_record_categories CASCADE'),
        RunSQL('DROP TABLE IF EXISTS child_health_categories CASCADE'),
        RunSQL('DROP TABLE IF EXISTS india_geo_data CASCADE'),
        RunSQL('DROP TABLE IF EXISTS thr_categories CASCADE'),
    ]
