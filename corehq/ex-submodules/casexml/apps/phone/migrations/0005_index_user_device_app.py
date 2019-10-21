from django.db import migrations

INDEX_NAME = 'phone_synclogsql_user_id_device_id_app_id_9616cbe2_idx'
COLUMNS = ','.join(["user_id", "device_id", "app_id"])
TABLE = 'phone_synclogsql'
CREATE_INDEX_SQL = f'CREATE INDEX CONCURRENTLY "{INDEX_NAME}" ON "{TABLE}" ({COLUMNS})'
DROP_INDEX_SQL = f'DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}'


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('phone', '0004_auto_20191021_1308'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AlterIndexTogether(
                    name='synclogsql',
                    index_together=set([('user_id', 'device_id', 'app_id')]),
                ),
            ]
        ),
    ]
