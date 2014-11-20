from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.reminders import PRODUCTS_NOT_SUBMITTED
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler


class UndoHandler(KeywordHandler):
    def help(self):
        return self.handle()

    def handle(self):
        all_prs = StockTransaction.objects.order_by('-report__date')
        if not all_prs:
            return self.respond(PRODUCTS_NOT_SUBMITTED)

        sp = all_prs[0].case_id
        sts = StockTransaction.objects.filter(product_id=all_prs[0].product_id)

        for st in sts:
            stock_transaction = StockTransaction.objects.get(case_id=sp, product_id=st.product_id)
            stock_transaction.quantity = st.quantity
            stock_transaction.save()
            st.delete()
            
        return self.respond(
            "Success. Your previous report has been removed. It was: %(report)s",
            report=sp)