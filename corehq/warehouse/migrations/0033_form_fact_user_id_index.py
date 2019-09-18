from django.db import migrations, models

FORM_STAGING_USER_INDEX_NAME = 'warehouse_f_user_id_785d18_idx'
COLUMNS = ['user_id']


CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})"
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY IF EXISTS {}"


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('warehouse', '0032_auto_20190917_1542'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL.format(
                FORM_STAGING_USER_INDEX_NAME,
                'warehouse_formstagingtable',
                ','.join(COLUMNS)
            ),
            reverse_sql=DROP_INDEX_SQL.format(FORM_STAGING_USER_INDEX_NAME),
            state_operations=[
                migrations.AddIndex(
                    model_name='formstagingtable',
                    index=models.Index(fields=COLUMNS, name=FORM_STAGING_USER_INDEX_NAME),
                ),
            ]
        ),
        migrations.RunSQL(
            sql=DROP_INDEX_SQL.format('warehouse_formstagingtable_received_on_6a73ba8d'),
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[
                migrations.AlterField(
                    model_name='formstagingtable',
                    name='received_on',
                    field=models.DateTimeField(),
                ),
            ]
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_formstagingtable_form_id_246fcaf3_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_formfact_form_id_1bb74f90_like'),
            migrations.RunSQL.noop
        ),
        # "warehouse_formstagingtable_timezone_idx" btree (timezone('UTC'::text, GREATEST(received_on, deleted_on, edited_on)))
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_formstagingtable_timezone_idx'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_domaindim_domain_id_b1c3504b_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_groupdim_group_id_b5f6f7bd_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_locationdim_location_id_bb42cee7_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_userdim_user_id_701f9e28_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_appstatusformstaging_domain_5997210f_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_appstatusforms_submission_build_version_0a62241a_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_appstatusformstaging_commcare_version_cfb94daf_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_appstatussynclogstaging_domain_2ab81363_like'),
            migrations.RunSQL.noop
        ),
        migrations.RunSQL(
            DROP_INDEX_SQL.format('warehouse_applicationstatusfact_domain_18a67251_like'),
            migrations.RunSQL.noop
        )
    ]
