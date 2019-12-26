# -*- coding: utf-8 -*-
# Generated by Django 1.11.26 on 2019-12-24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0156_auto_20191217_0932'),
    ]

    operations = [
        migrations.RunSQL('ALTER TABLE icds_dashboard_adolescent_girls_registration DROP CONSTRAINT  icds_dashboard_adolescen_supervisor_id_person_cas_de4d929b_uniq;'),
        migrations.RunSQL('ALTER TABLE "icds_dashboard_adolescent_girls_registration" ADD CONSTRAINT "icds_dashboard_adolescen_supervisor_id_person_cas_de4d929b_uniq" UNIQUE ("month", "supervisor_id","person_case_id" );'),
        migrations.RunSQL('CREATE UNIQUE INDEX icds_dashboard_adolescent_girls_registration_month_supervisor_id_person_case_id_uniq on "icds_dashboard_adolescent_girls_registration" (month,supervisor_id,person_case_id);'),
        migrations.RunSQL('ALTER TABLE "icds_dashboard_adolescent_girls_registration" DROP CONSTRAINT IF EXISTS icds_dashboard_adolescent_girls_registration_pkey;'),
        migrations.RunSQL('ALTER TABLE "icds_dashboard_adolescent_girls_registration" ADD CONSTRAINT icds_dashboard_adolescent_girls_registration_pkey PRIMARY KEY USING INDEX icds_dashboard_adolescent_girls_registration_month_supervisor_id_person_case_id_uniq;')
    ]
