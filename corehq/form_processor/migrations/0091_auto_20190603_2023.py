# Generated by Django 1.11.20 on 2019-06-03 20:23

from django.db import migrations, models


TABLE_NAME = 'form_processor_ledgertransaction'
INDEX_NAME = 'form_proces_form_id_86572d_idx'
COLUMNS = ['form_id']

CREATE_INDEX_SQL = "CREATE INDEX CONCURRENTLY IF NOT EXISTS {} ON {} ({})".format(
    INDEX_NAME, TABLE_NAME, ','.join(COLUMNS))
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY IF EXISTS {}".format(INDEX_NAME)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('form_processor', '0090_auto_20190523_0833'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AddIndex(
                    model_name='ledgertransaction',
                    index=models.Index(fields=['form_id'], name=INDEX_NAME),
                ),
            ]
        )
    ]
