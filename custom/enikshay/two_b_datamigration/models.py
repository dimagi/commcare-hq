from __future__ import absolute_import
from django.db import models


class MigratedDRTBCaseCounter(models.Model):
    id = models.AutoField(primary_key=True)

    @classmethod
    def get_next_counter(cls):
        counter = MigratedDRTBCaseCounter.objects.create()
        return counter.id
