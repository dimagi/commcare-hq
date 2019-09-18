from django.db import migrations, models

TABLE_NAME = 'warehouse_formstagingtable'
INDEX_NAME = 'warehouse_f_user_id_785d18_idx'
COLUMNS = ['user_id']


CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS)
)
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY {}".format(INDEX_NAME)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('warehouse', '0032_auto_20190917_1542'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AddIndex(
                    model_name='formstagingtable',
                    index=models.Index(fields=['user_id'], name=INDEX_NAME),
                ),
            ]
        ),
    ]
