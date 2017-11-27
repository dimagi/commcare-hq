from __future__ import absolute_import, print_function

import traceback

import gevent
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor, iter_all_ids
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked
from six.moves import input


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
                g = gevent.spawn(_update_forms_in_db, db_name, False)
                greenlets.append(g)

            gevent.joinall(greenlets)
            try:
                for job in greenlets:
                    job.get()
            except Exception:
                traceback.print_exc()


def _update_forms_in_db(db_name, online=True):
    reindex_accessor = FormReindexAccessor(limit_db_aliases=[db_name])
    doc_count = reindex_accessor.get_approximate_doc_count(db_name)
    doc_iterator = iter_all_ids(reindex_accessor)
    with_progress = with_progress_bar(doc_iterator, length=doc_count, oneline=online)
    for form_ids in chunked(with_progress, 1000):
        _update_forms(db_name, form_ids)


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
                union
                select form_id, max(date) as modified_on from form_processor_xformoperationsql group by form_id
                ) as d group by form_id
        )
        UPDATE form_processor_xforminstancesql SET modified_on = max_dates.modified_on
        FROM max_dates
        WHERE form_processor_xforminstancesql.form_id = max_dates.form_id
          AND form_processor_xforminstancesql.form_id in %s
        """, [form_ids])


def confirm(msg):
    return input(msg + "\n(y/n)") == 'y'
