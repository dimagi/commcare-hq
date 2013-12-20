from datetime import datetime
from django.db import models


class StockReport(models.Model):
    form_id = models.CharField(max_length=100, db_index=True)
    date = models.DateTimeField(default=datetime.utcnow, db_index=True)


class StockTransaction(models.Model):
    report_id = models.ForeignKey(StockReport)
    # for now, a supply point or requisition case
    case_id = models.CharField(max_length=100, db_index=True)
    product_id = models.CharField(max_length=100, db_index=True)
    quantity = models.FloatField()

