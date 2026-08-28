from django.db import migrations

INDEX_NAME = 'builds_comm_couch_i_3b9fc6_idx'
DROP_INDEX_SQL = f'DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}'
CREATE_INDEX_SQL = (
    f'CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} '
    f'ON builds_commcaremobilebuild (couch_id)'
)

class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('builds', '0003_remove_commcaremobilebuild_couch_id'),
    ]
    operations = [
        migrations.RunSQL(
            sql=DROP_INDEX_SQL,
            reverse_sql=CREATE_INDEX_SQL,
            state_operations=[
                migrations.RemoveIndex(
                    model_name='commcaremobilebuild',
                    name=INDEX_NAME,
                ),
            ],
        ),
        migrations.RunSQL(
            sql="ALTER TABLE builds_commcaremobilebuild DROP COLUMN couch_id;",
            reverse_sql="ALTER TABLE builds_commcaremobilebuild ADD COLUMN couch_id VARCHAR(126);"
        )

    ]