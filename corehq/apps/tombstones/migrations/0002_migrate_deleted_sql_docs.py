from collections import defaultdict

from django.conf import settings
from django.db import migrations

from corehq.apps.cleanup.models import DeletedSQLDoc
from corehq.apps.tombstones.models import Tombstone
from corehq.sql_db.config import plproxy_config
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
from corehq.util.django_migrations import skip_on_fresh_install

BATCH_SIZE = 1000


@skip_on_fresh_install
def copy_deleted_sql_docs_to_tombstones(apps, schema_editor):
    if settings.USE_PARTITIONED_DATABASE:
        # On partitioned envs the migration runs on the proxy db and each shard db,
        # so ensure we only copy data once, when running on the proxy db
        if schema_editor.connection.alias != plproxy_config.proxy_db:
            return

    queryset = DeletedSQLDoc.objects.all().order_by('id')

    by_shard = defaultdict(list)
    pending = 0
    total = 0
    for doc in queryset.iterator(chunk_size=BATCH_SIZE):
        db_alias = get_db_alias_for_partitioned_doc(doc.doc_id)
        by_shard[db_alias].append(
            Tombstone(
                doc_id=doc.doc_id,
                object_class_path=doc.object_class_path,
                domain=doc.domain,
                deleted_on=doc.deleted_on,
            )
        )
        pending += 1
        if pending >= BATCH_SIZE:
            _bulk_save(by_shard)
            total += pending
            pending = 0
    _bulk_save(by_shard)
    total += pending
    print(f"Created {total} Tombstone records")


def _bulk_save(by_shard):
    for db_alias, tombstones in by_shard.items():
        if tombstones:
            Tombstone.objects.using(db_alias).bulk_create(tombstones)
    by_shard.clear()


class Migration(migrations.Migration):
    dependencies = [
        ('tombstones', '0001_create_tombstone_model'),
        ('cleanup', '0019_alter_deletedsqldoc_table'),
    ]

    operations = [
        migrations.RunPython(
            copy_deleted_sql_docs_to_tombstones,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
