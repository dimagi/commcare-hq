from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0016_add_deletedsqldoc'),
    ]

    operations = [
        migrations.RunSQL("""
            DROP TABLE IF EXISTS "oauth_integrations_googleapitoken" CASCADE;
            DROP TABLE IF EXISTS "oauth_integrations_livegooglesheetrefreshstatus" CASCADE;
            DROP TABLE IF EXISTS "oauth_integrations_livegooglesheetschedule" CASCADE;
        """),
    ]


"""
Dropped entities can be checked with the following query:
    select pg_describe_object(classid, objid, objsubid)
    from pg_depend
    where refobjid in (
        'oauth_integrations_googleapitoken'::regclass,
        'oauth_integrations_livegooglesheetrefreshstatus'::regclass,
        'oauth_integrations_livegooglesheetschedule'::regclass
    );
Example output (from staging, the same as a local dev setup):
 type oauth_integrations_livegooglesheetschedule
 type oauth_integrations_livegooglesheetrefreshstatus
 type oauth_integrations_googleapitoken
 toast table pg_toast.pg_toast_2980995
 toast table pg_toast.pg_toast_2980982
 toast table pg_toast.pg_toast_2892669
 sequence oauth_integrations_livegooglesheetschedule_id_seq
 sequence oauth_integrations_livegooglesheetrefreshstatus_id_seq
 sequence oauth_integrations_googleapitoken_id_seq
 index oauth_integrations_livegoo_schedule_id_064aa4f4
 index oauth_integrations_livegoo_export_config_id_200127ab
 index oauth_integrations_liveg_export_config_id_200127ab_like
 index oauth_integrations_googleapitoken_user_id_9d01255f
 default value for column id of table oauth_integrations_livegooglesheetschedule
 default value for column id of table oauth_integrations_livegooglesheetrefreshstatus
 default value for column id of table oauth_integrations_googleapitoken
 constraint oauth_integrations_livegooglesheetschedule_pkey on table oauth_integrations_livegooglesheetschedule
 constraint oauth_integrations_livegooglesheetrefreshstatus_pkey on table oauth_integrations_livegooglesheetrefreshstatus
 constraint oauth_integrations_l_schedule_id_064aa4f4_fk_oauth_int on table oauth_integrations_livegooglesheetrefreshstatus
 constraint oauth_integrations_googleapitoken_pkey on table oauth_integrations_googleapitoken
 constraint oauth_integrations_g_user_id_9d01255f_fk_auth_user on table oauth_integrations_googleapitoken
"""
