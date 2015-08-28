from collections import defaultdict
from casexml.apps.stock.const import COMMTRACK_REPORT_XMLNS
from casexml.apps.stock.models import StockReport
from couchforms.models import XFormInstance
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler


class UndoHandler(KeywordHandler):
    def help(self):
        return self.handle()

    def get_user_latest_report(self, user):
        xform = XFormInstance.view(
            'reports_forms/all_forms',
            startkey=['submission xmlns user', self.domain, COMMTRACK_REPORT_XMLNS, user.get_id, {}],
            endkey=['submission xmlns user', self.domain, COMMTRACK_REPORT_XMLNS, user.get_id],
            reduce=False,
            include_docs=True,
            descending=True
        ).first()
        if not xform:
            return
        return StockReport.objects.filter(form_id=xform.get_id)

    def restore_message_from_transactions(self, transactions):
        product_dict = defaultdict(lambda: {'soh': None, 'receipts': 0})

        for tx in transactions:
            if tx.type == 'receipts':
                product_dict[tx.sql_product.code]['receipts'] = int(tx.quantity)
            elif tx.type == 'stockonhand':
                product_dict[tx.sql_product.code]['soh'] = int(tx.stock_on_hand)

        return 'soh' + ' ' + ' '.join(
            [
                '{} {}.{}'.format(code, product_dict[code]['soh'], product_dict[code]['receipts'])
                for code in sorted(product_dict.keys())
            ]
        )

    def handle(self):
        last_reports = self.get_user_latest_report(self.user)

        if not last_reports:
            self.respond('You have not submitted any product reports yet.')
            return True

        transactions = []
        for report in last_reports:
            transactions.extend(report.stocktransaction_set.all())

        message = self.restore_message_from_transactions(transactions)
        for last_report in last_reports:
            last_report.delete()
        self.respond("Success. Your previous report has been removed. It was: %(report)s", report=message)
        return True
