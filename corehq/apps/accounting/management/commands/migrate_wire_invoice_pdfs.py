from django.core.management import BaseCommand

from dimagi.utils.couch.database import iter_docs
from corehq.apps.accounting.models import InvoicePdf, WireBillingRecord
from corehq.util.couch import IterDB


class Command(BaseCommand):
    help = ("Migrate InvoicePdfs to have is_wire field")

    def handle(self, *args, **options):
        invoice_ids = WireBillingRecord.objects.values_list('pdf_data_id', flat=True)
        db = InvoicePdf.get_db()

        with IterDB(db) as iter_db:
            for doc in iter_docs(db, invoice_ids):
                doc['is_wire'] = True
                iter_db.save(doc)

        if iter_db.saved_ids:
            print '{}/{} docs saved correctly!'.format(len(iter_db.saved_ids), len(invoice_ids))
        if iter_db.error_ids:
            print 'There were {} errors. There were errors when saving the following:'.format(
                len(iter_db.error_ids)
            )
            for error_id in iter_db.error_ids:
                print error_id
