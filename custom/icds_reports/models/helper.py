from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models


class ChildHealthCategories(models.Model):
    gender = models.TextField()
    age_tranche = models.TextField()
    caste = models.TextField()
    disabled = models.TextField()
    minority = models.TextField()
    resident = models.TextField()

    class Meta:
        app_label = 'icds_model'
        db_table = 'child_health_categories'
        managed = False
        unique_together = (('gender', 'age_tranche', 'caste', 'disabled', 'minority', 'resident'),)

class CcsRecordCategories(models.Model):
    ccs_status = models.TextField()
    trimester = models.TextField(blank=True, null=True)
    caste = models.TextField()
    disabled = models.TextField()
    minority = models.TextField()
    resident = models.TextField()

    class Meta:
        app_label = 'icds_model'
        db_table = 'ccs_record_categories'
        managed = False


class ThrCategories(models.Model):
    beneficiary_type = models.TextField()
    caste = models.TextField()
    disabled = models.TextField()
    minority = models.TextField()
    resident = models.TextField()

    class Meta:
        app_label = 'icds_model'
        db_table = 'thr_categories'
        managed = False        


class IcdsMonths(models.Model):
    month_name = models.TextField(primary_key=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        app_label = 'icds_model'
        db_table = 'icds_months'
        managed = False 


class IndiaGeoData(models.Model):
    state_site_code = models.TextField()
    district_site_code = models.TextField()
    PointID = models.IntegerField()
    PolygonID = models.IntegerField()
    SubPolygonID = models.IntegerField()
    longitude = models.DecimalField()
    latitude = models.DecimalField()

    class Meta:
        app_label = 'icds_model'
        db_table = 'india_geo_data'
        managed = False
