from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models


class AggregateSQLProfile(models.Model):
    name = models.TextField()
    date = models.DateField(auto_now=True)
    duration = models.PositiveIntegerField()


class UcrTableNameMapping(models.Model):
    table_type = models.TextField(primary_key=True)
    table_name = models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'icds_model'
        managed = False
        db_table = 'ucr_table_name_mapping'
