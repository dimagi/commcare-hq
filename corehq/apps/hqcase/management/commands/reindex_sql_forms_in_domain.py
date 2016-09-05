from django.core.management import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import *
from corehq.pillows.xform import *


def reindex_sql_forms_in_domain(domain):
    for state, _ in XFormInstanceSQL.STATES:
        doc_ids = FormAccessorSQL.get_form_ids_in_domain_by_state(domain, state)
        for form in FormAccessorSQL.get_forms(doc_ids):
            form_json = form.to_json(include_attachments=True)
            txform = transform_xform_for_elasticsearch(form_json)
            reindexer = get_sql_form_reindexer()
            reindexer.doc_processor.process_bulk_docs([txform])


class Command(BaseCommand):
    args = 'domain'
    help = 'Reindex a pillowtop index'

    def handle(self, domain, *args, **options):
        reindex_sql_forms_in_domain(domain)
