from django.db.models import Q
from django.core.management.base import BaseCommand

from corehq.form_processor.models import XFormInstance
from corehq.sql_db.util import (
    paginate_query_across_partitioned_databases,
    split_list_by_db_partition,
)

from dimagi.utils.chunked import chunked


class Command(BaseCommand):
    help = "One time use to populate missing XFormInstance.deleted_on values"

    def handle(self, **options):
        chunk_size = 100
        old_deleted_state = 64

        def iter_all_ids():
            rows = paginate_query_across_partitioned_databases(
                XFormInstance,
                Q(deleted_on__isnull=True, state__gte=old_deleted_state),
                values=['form_id'],
                query_size=chunk_size,
            )
            for r in rows:
                yield r[0]

        form_ids = iter_all_ids()
        for chunk in chunked(form_ids, chunk_size, list):
            for db, forms_by_db in split_list_by_db_partition(chunk):
                with XFormInstance.get_cursor_for_partition_db(db) as cursor:
                    cursor.execute(
                        """
                        UPDATE form_processor_xforminstancesql
                        SET deleted_on = server_modified_on
                        WHERE form_id = ANY(%s)
                            AND deleted_on IS NULL
                            AND state & %s = %s
                        """,
                        [forms_by_db, old_deleted_state, old_deleted_state]
                    )
