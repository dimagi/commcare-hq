# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0113_service_delivery_dashboard'),
    ]

    operations = [
        migrations.RunSQL('CREATE TABLE IF NOT EXISTS "icds_months_local" (LIKE "icds_months" INCLUDING ALL)'),
        migrations.RunSQL('CREATE TABLE IF NOT EXISTS "awc_location_local" (LIKE "awc_location" INCLUDING ALL)')
    ]
