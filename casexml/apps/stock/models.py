from datetime import datetime
from django.db import models


class StockReport(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    date = models.DateTimeField(db_index=True)
    type = models.CharField(max_length=10)  # currently "balance" or "transfer"

    # todo: there are properties like these that could be really useful for queries
    # and reports - should decide which ones we want to add if any.
    # they are all redundant via form_id linkage

    # server_date = models.DateTimeField(default=datetime.utcnow, db_index=True)
    # user_id = models.CharField(max_length=100, db_index=True)

    def __repr__(self):
        return '{type} on {date} ({form})'.format(type=self.type, date=self.date, form=self.form_id)

class StockTransaction(models.Model):
    report = models.ForeignKey(StockReport)
    # for now, a supply point or requisition case
    case_id = models.CharField(max_length=100, db_index=True)
    product_id = models.CharField(max_length=100, db_index=True)

    # often one of these two will be derived based on the other one
    quantity = models.FloatField(null=True)
    stock_on_hand = models.FloatField()

    def __repr__(self):
        return 'stock transfer of {quantity} to {soh} (case: {case}, product: {product})'.format(
            quantity=self.quantity, soh=self.stock_on_hand, case=self.case_id, product=self.product_id,
        )

    def get_previous_transaction(self):
        siblings = StockTransaction._peer_qs(self.case_id, self.product_id).exclude(pk=self.pk)
        if siblings.count():
            return siblings[0]

    @classmethod
    def latest(cls, case_id, product_id):
        relevant = cls._peer_qs(case_id, product_id)
        if relevant.count():
            return relevant[0]
        return None

    @classmethod
    def _peer_qs(self, case_id, product_id):
        return StockTransaction.objects.filter(case_id=case_id, product_id=product_id).order_by('-report__date')
