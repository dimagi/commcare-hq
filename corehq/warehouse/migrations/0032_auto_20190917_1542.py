from django.db import migrations, models

TABLE_NAME = 'warehouse_synclogstagingtable'
INDEX_NAME = 'warehouse_s_user_id_8bcfbf_idx'
COLUMNS = ['user_id']


CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS)
)
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY {}".format(INDEX_NAME)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('warehouse', '0031_unique_app_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='formfact',
            name='state',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'normal'), (2, 'archived'), (4, 'deprecated'), (8, 'duplicate'), (16, 'error'),
                         (32, 'submission_error'), (64, 'deleted')]),
        ),
        migrations.AlterField(
            model_name='formstagingtable',
            name='state',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'normal'), (2, 'archived'), (4, 'deprecated'), (8, 'duplicate'), (16, 'error'),
                         (32, 'submission_error'), (64, 'deleted')], default=1),
        ),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AddIndex(
                    model_name='synclogstagingtable',
                    index=models.Index(fields=['user_id'], name='warehouse_s_user_id_8bcfbf_idx'),
                ),
            ]
        ),
    ]
