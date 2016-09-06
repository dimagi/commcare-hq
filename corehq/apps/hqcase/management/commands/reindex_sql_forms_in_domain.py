from dimagi.utils.chunked import chunked
from django.core.management import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import *
from corehq.pillows.xform import *


def reindex_sql_forms_in_domain(domain):
    reindexer = get_sql_form_reindexer()

    for state, _ in XFormInstanceSQL.STATES:
        all_doc_ids = FormAccessorSQL.get_form_ids_in_domain_by_state(domain, state)
        for doc_ids in chunked(all_doc_ids, 100):
            print 'Reindexing doc_ids: {}'.format(','.join(doc_ids))
            reindexer.doc_processor.process_bulk_docs([
                transform_xform_for_elasticsearch(form.to_json(include_attachments=True))
                for form in FormAccessorSQL.get_forms(list(doc_ids))
            ])


class Command(BaseCommand):
    args = 'domain'
    help = 'Reindex a pillowtop index'

    def handle(self, domain, *args, **options):
        reindex_sql_forms_in_domain(domain)
