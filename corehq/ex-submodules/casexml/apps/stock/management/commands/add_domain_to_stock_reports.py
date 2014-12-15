from django.core.management import BaseCommand
from optparse import make_option

from casexml.apps.stock.models import StockReport
from couchforms.models import XFormInstance


class Command(BaseCommand):
    help = "Populates the 'domain' field of StockReports."

    def handle(self, *args, **options):
        for stock_report in StockReport.objects.all():
            form = XFormInstance.get(stock_report.form_id)
            stock_report.domain = form.domain
            stock_report.save()
