from django.db import models
from django.contrib.postgres.fields import ArrayField


class PartnerAnalyticsContact(models.Model):
    organization_name = models.CharField(max_length=127, db_index=True)
    emails = ArrayField(
        models.EmailField(),
        default=list
    )


class PartnerAnalyticsDataPoint(models.Model):
    slug = models.CharField(max_length=127, db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    year = models.IntegerField()
    month = models.IntegerField()
    value = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['slug', 'domain', 'year', 'month'],
                name='unique_per_month'
            )
        ]


class PartnerAnalyticsReport(models.Model):
    contact = models.ForeignKey(PartnerAnalyticsContact, on_delete=models.CASCADE)
    title = models.CharField(max_length=127, db_index=True, unique=True)
    data_slug = models.CharField(max_length=127, db_index=True)
    domains = ArrayField(
        models.CharField(max_length=255),
        default=list
    )
