# Generated by Django 1.11.16 on 2019-10-10

from django.db import migrations

from corehq.sql_db.operations import RawSQLMigration

migrator = RawSQLMigration(('custom', 'icds_reports', 'migrations', 'sql_templates', 'database_views'))


class Migration(migrations.Migration):

    dependencies = [
        ('icds_reports', '0151_fix_sdd_view')
    ]

    operations = [
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_1g_dpt_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_2g_dpt_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_3g_dpt_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_5g_dpt_booster DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_5g_dpt_booster1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_7gdpt_booster_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_0g_hep_b_0 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_1g_hep_b_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_2g_hep_b_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_3g_hep_b_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_3g_ipv DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_4g_je_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_5g_je_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_5g_measles_booster DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_4g_measles DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_0g_opv_0 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_1g_opv_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_2g_opv_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_3g_opv_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_5g_opv_booster DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_1g_penta_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_2g_penta_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_3g_penta_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_1g_rv_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_2g_rv_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_3g_rv_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_4g_vit_a_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_5g_vit_a_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_6g_vit_a_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_6g_vit_a_4 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_6g_vit_a_5 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_6g_vit_a_6 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_6g_vit_a_7 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_6g_vit_a_8 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_7g_vit_a_9 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_anc_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_anc_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_anc_3 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_anc_4 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_tt_1 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_tt_2 DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_tt_booster DATE"),
        migrations.RunSQL("ALTER table child_health_monthly ADD COLUMN due_list_date_1g_bcg DATE"),
        migrator.get_migration('child_health_monthly.sql')
    ]
