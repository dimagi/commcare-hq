from django.db import migrations

TABLE_NAME = 'blobs_blobmeta'
INDEX_NAME = 'blobs_blobmeta_type_created_on_idx'
COLUMNS = ['type', 'created_on']

CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS))
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY IF EXISTS {}".format(INDEX_NAME)


class Migration(migrations.Migration):

    dependencies = [
        ('icds', '0006_hostedccz_status'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
        )
    ]
