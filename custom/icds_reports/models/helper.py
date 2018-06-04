from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models

class IcdsMonths(models.Model):
    month_name = models.TextField(primary_key=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        managed = False
        db_table = 'icds_months'
