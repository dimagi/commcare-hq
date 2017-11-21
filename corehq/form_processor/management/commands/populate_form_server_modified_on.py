from __future__ import absolute_import
import os

from django.core.management.base import LabelCommand, CommandError
from django.db import connections
from django.template import Engine
from django.conf import settings

from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
from corehq.form_processor.models import XFormInstanceSQL

SQL_ACCESSOR_DIR = os.path.join(settings.FILEPATH, 'corehq', 'sql_accessors', 'sql_templates')

SQL_PROXY_ACCESSOR_DIR = os.path.join(settings.FILEPATH, 'corehq', 'sql_proxy_accessors', 'sql_templates')
TEMPLATE_NAME = '_template.sql'


class Command(LabelCommand):
    help = "Create a template sql function"

    def add_arguments(self, parser):
        parser.add_argument('db_name')

    def handle_label(self, db_name, **options):
        accessor = FormReindexAccessor(ids_only=True)
        if db_name not in accessor.sql_db_aliases:
            raise CommandError('db_name must be one of: {}'.format(accessor.sql_db_aliases))

        doc_ids = list(accessor.get_docs(db_name))
        while doc_ids:
            cursor = connections[db_name].cursor()
            cursor.execute("""
            UPDATE f SET f.server_modified_on = m.modified_on
            FROM {form_table} as f INNER JOIN (
              SELECT form_id, max(modified_on) as modified_on FROM (
                  SELECT form_id, 
                    CASE WHEN deleted_on is not NULL THEN deleted_on
                    WHEN edited_on is not NULL AND edited_on > received_on THEN edited_on
                    ELSE received_on END as modified_on
                  FROM {form_table} WHERE form_id = ANY(%s)
                  UNION
                  SELECT form_id, max(date) as modified_on FROM {operation_table} WHERE form_id = ANY(%s) GROUP BY form_id
              ) as dates GROUP BY form_id
            ) as m
            ON f.form_id = m.form_id
            """, doc_ids)

            """
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
FROM max_dates WHERE form_processor_xforminstancesql.form_id = max_dates.form_id;
"""
