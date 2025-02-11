from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cleanup', '0017_delete_oauth_integrations_models'),
    ]

    operations = [
        migrations.RunSQL("""
            DROP TABLE IF EXISTS "ewsghana_facilityincharge" CASCADE;
            DROP TABLE IF EXISTS "ewsghana_ewsextension" CASCADE;
            DROP TABLE IF EXISTS "ewsghana_sqlnotification" CASCADE;
        """),
    ]


"""
Dropped entities can be checked with the following query:
    select pg_describe_object(classid, objid, objsubid)
    from pg_depend
    where refobjid in (
        'ewsghana_facilityincharge'::regclass,
        'ewsghana_ewsextension'::regclass,
        'ewsghana_sqlnotification'::regclass
    );
Example output (from production):
 type ewsghana_ewsextension
 sequence ewsghana_ewsextension_id_seq
 type ewsghana_facilityincharge
 sequence ewsghana_facilityincharge_id_seq
 type ewsghana_sqlnotification
 sequence ewsghana_sqlnotification_id_seq
 default value for column id of table ewsghana_ewsextension
 default value for column id of table ewsghana_facilityincharge
 default value for column id of table ewsghana_sqlnotification
 constraint ewsghana_ewsextension_pkey on table ewsghana_ewsextension
 constraint ewsghana_facilityincharge_pkey on table ewsghana_facilityincharge
 constraint ewsghana_sqlnotification_pkey on table ewsghana_sqlnotification
 index ewsghana_ewsextension_e274a5da
 index ewsghana_ewsextension_e8701ad4
 index ewsghana_ewsextension_location_id_636bec0358987f83_like
 index ewsghana_ewsextension_user_id_6cff5f4a22d0e14b_like
 index ewsghana_facilityincharge_location_id
 index ewsghana_facilityincharge_user_id
 index ewsghana_facilityincharge_user_id_like
 constraint ewsgha_location_id_4879eb14d7a4a143_fk_locations_sqllocation_id on table ewsghana_facilityincharge
(20 rows)
"""
