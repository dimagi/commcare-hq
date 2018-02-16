from __future__ import absolute_import
from django.db import models


class MigratedBeneficiaryCounter(models.Model):
    id = models.AutoField(primary_key=True)

    @classmethod
    def get_next_counter(cls):
        counter = MigratedBeneficiaryCounter.objects.create()
        return counter.id
