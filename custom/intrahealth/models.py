from django.db import models


class PaymentTracking(models.Model):
    """
    Model for payment tracking.
    """

    case_id = models.CharField(max_length=100, db_index=True)
    month = models.IntegerField()
    year = models.IntegerField()
    calculated_amount_owed = models.IntegerField(default=0)
    actual_amount_owed = models.IntegerField(default=0)
    amount_paid = models.IntegerField(default=0)
