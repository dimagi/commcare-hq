from __future__ import absolute_import
from __future__ import print_function

from __future__ import unicode_literals
import csv
from datetime import datetime

import pytz
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from corehq.apps.userreports.document_stores import get_document_store
from corehq.apps.userreports.models import get_datasource_config
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Find rows in a datasource that aren't what they should be"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('data_source_id')

    def handle(self, domain, data_source_id, *args, **kwargs):
        config, _ = get_datasource_config(data_source_id, domain)
        adapter = get_indicator_adapter(config)
        q = adapter.get_query_object()
        document_store = get_document_store(domain, config.referenced_doc_type)
        bad_rows = []
        for row in with_progress_bar(q, length=q.count()):
            doc_id = row.doc_id
            doc = document_store.get_document(doc_id)

            current_rows = config.get_all_values(doc)
            if len(current_rows) > 1:
                raise ValueError("this command doesn't work for datasources returning multiple rows per doc")

            try:
                current_row = current_rows[0]
            except KeyError:
                continue

            # don't compare the 'inserted_at' columns
            current_row = [val for val in current_row if val.column.database_column_name != 'inserted_at']

            for val in current_row:
                try:
                    inserted_value = getattr(row, val.column.database_column_name)
                    if (inserted_value != val.value
                       or row.inserted_at.replace(tzinfo=pytz.utc) < parse_datetime(doc['server_modified_on'])):
                        bad_rows.append({
                            'doc_id': row.doc_id,
                            'column_name': val.column.database_column_name,
                            'inserted_at': row.inserted_at.isoformat(),
                            'server_modified_on': doc['server_modified_on'],
                            'stored_value': getattr(row, val.column.database_column_name),
                            'desired_value': val.value,
                            'message': ('column mismatch'
                                        if inserted_value != val.value else "modified date early"),
                        })
                except AttributeError:
                    bad_rows.append({
                        'doc_id': row.doc_id,
                        'column_name': val.column.database_column_name,
                        'inserted_at': 'missing',
                        'server_modified_on': doc['server_modified_on'],
                        'stored_value': 'missing',
                        'desired_value': val.value,
                        'message': 'doc missing',
                    })

        filename = 'datasource_mismatches_{}_{}.csv'.format(
            data_source_id[-8:],
            datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
        )
        with open(filename, 'w') as f:
            headers = ['doc_id', 'column_name', 'inserted_at', 'server_modified_on',
                       'stored_value', 'desired_value', 'message']
            writer = csv.DictWriter(f, headers)
            writer.writeheader()
            writer.writerows(bad_rows)

        print("Found {} mismatches. Check {} for more details".format(len(bad_rows), filename))
