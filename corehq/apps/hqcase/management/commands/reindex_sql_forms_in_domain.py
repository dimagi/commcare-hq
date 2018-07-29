from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import *
from corehq.pillows.xform import SqlFormReindexerFactory


def reindex_sql_forms_in_domain(domain):
    reindexer = SqlFormReindexerFactory().build()

    for state, _ in XFormInstanceSQL.STATES:
        all_doc_ids = FormAccessorSQL.get_form_ids_in_domain_by_state(domain, state)
        for doc_ids in chunked(all_doc_ids, 100):
            print('Reindexing doc_ids: {}'.format(','.join(doc_ids)))
            reindexer.doc_processor.process_bulk_docs([
                reindexer.reindex_accessor.doc_to_json(form)
                for form in FormAccessorSQL.get_forms(list(doc_ids))
            ])


class Command(BaseCommand):
    help = 'Reindex a pillowtop index'

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, *args, **options):
        reindex_sql_forms_in_domain(domain)
