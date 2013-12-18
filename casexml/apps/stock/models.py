import datetime
from django.db import models


class StockReport(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    date = models.DateTimeField(default=datetime.utcnow)

    class Meta:
        abstract = True


class BalanceReport(StockReport):
    # for now, a supply point or requisition case
    case_id = models.CharField(max_length=100, db_index=True)


class TransferReport(StockReport):
    source_id = models.CharField(max_length=100, db_index=True)
    destination_id = models.CharField(max_length=100, db_index=True)


class StockDetails(models.Model):
    product_id = models.CharField(max_length=100, db_index=True)
    quantity = models.FloatField()

    class Meta:
        abstract = True


class BalanceDetails(StockDetails):
    report_id = models.ForeignKey(BalanceReport)


class TransferDetails(StockDetails):
    report_id = models.ForeignKey(TransferReport)
