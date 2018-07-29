from __future__ import absolute_import, print_function

from __future__ import unicode_literals
import traceback

import gevent
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from six.moves import input

from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor, iter_all_ids_chunked
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


class Command(BaseCommand):
    help = "Create simple mock data in a domain."

    def add_arguments(self, parser):
        parser.add_argument('-d', '--db_name', help='Django DB alias to run on')

    def handle(self, db_name, **options):
        db_names = get_db_aliases_for_partitioned_query()
        if db_name or len(db_names) == 1:
            _update_forms_in_db(db_name or db_names[0])
        else:
            if not confirm('Running without "db_name" will execute on ALL databases in parallel. Continue?'):
                raise CommandError('abort')

            greenlets = []
            for db_name in db_names:
                g = gevent.spawn(_update_forms_in_db, db_name)
                greenlets.append(g)

            gevent.joinall(greenlets)
            try:
                for job in greenlets:
                    job.get()
            except Exception:
                traceback.print_exc()


def _update_forms_in_db(db_name):
    reindex_accessor = FormReindexAccessor(limit_db_aliases=[db_name])
    doc_count = reindex_accessor.get_approximate_doc_count(db_name)
    chunks = iter_all_ids_chunked(reindex_accessor)
    processed = 0
    for form_ids in chunks:
        processed += len(form_ids)
        _update_forms(db_name, tuple(form_ids))

        if processed % 5000 == 0:
            print('[progress] [%s] %s of %s' % (db_name, processed, doc_count))

    print('[progress] [%s] Complete' % db_name)


def _update_forms(db_name, form_ids):
    with connections[db_name].cursor() as cursor:
        cursor.execute("""
        WITH max_dates as (
            SELECT form_id, max(modified_on) as modified_on FROM (
                     SELECT form_id,
                        CASE WHEN deleted_on is not NULL THEN deleted_on
                        WHEN edited_on is not NULL AND edited_on > received_on THEN edited_on
                        ELSE received_on END as modified_on
                        FROM form_processor_xforminstancesql
                        WHERE form_processor_xforminstancesql.form_id in %(form_ids)s
                union
                select form_id, max(date) as modified_on from form_processor_xformoperationsql
                where form_processor_xformoperationsql.form_id in %(form_ids)s
                group by form_id
                ) as d group by form_id
        )
        UPDATE form_processor_xforminstancesql SET server_modified_on = max_dates.modified_on
        FROM max_dates
        WHERE form_processor_xforminstancesql.form_id = max_dates.form_id
        """, {'form_ids': form_ids})


def confirm(msg):
    return input(msg + "\n(y/n)") == 'y'
