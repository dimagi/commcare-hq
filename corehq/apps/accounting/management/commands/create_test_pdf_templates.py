from django.core.management import BaseCommand

from corehq.apps.accounting.tests.test_invoice_pdf import InvoiceRenderer


class Command(BaseCommand):
    help = """Writes new reference PDF files (to make tests pass again)"""

    def handle(self, **options):
        renderer = InvoiceRenderer()
        for fpath, rendered in renderer.iter_invoices():
            with open(fpath, "wb") as pdf_out:
                pdf_out.write(rendered.getvalue())
