from django.db import migrations
from django.db.models import Index, Q

from corehq.sql_db.migrations import partitioned
CREATE_INDEX_SQL = """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS "blobs_blobmeta_type_co_23e226"
    ON "blobs_blobmeta" ("type_code", "created_on")
    WHERE "blobs_blobmeta"."domain" = 'icds-cas'
"""
DROP_INDEX_SQL = "DROP INDEX CONCURRENTLY IF EXISTS blobs_blobmeta_type_co_23e226"


@partitioned
class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('blobs', '0009_delete_blobexpiration'),
    ]

    operations = [
        migrations.RunSQL(migrations.RunSQL.noop, migrations.RunSQL.noop, state_operations=[
            migrations.RemoveIndex(
                model_name='blobmeta',
                name='blobs_blobmeta_expires_64b92d',
            ),
            migrations.AddIndex(
                model_name='blobmeta',
                index=Index(
                    fields=['expires_on'],
                    name='blobs_blobmeta_expires_ed7e3d',
                    condition=Q(expires_on__isnull=False),
                ),
            )
        ]),
        migrations.RunSQL(
            sql=CREATE_INDEX_SQL,
            reverse_sql=DROP_INDEX_SQL,
            state_operations=[
                migrations.AddIndex(
                    model_name='blobmeta',
                    index=Index(
                        fields=['type_code', 'created_on'],
                        name='blobs_blobmeta_type_co_23e226',
                        condition=Q(domain='icds-cas'),
                    ),
                ),
            ]
        ),
    ]
