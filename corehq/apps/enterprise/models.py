from django.db import models
from django.contrib.postgres.fields import ArrayField


class EnterprisePermissions(models.Model):
    account = models.ForeignKey('accounting.BillingAccount', null=False, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=False)
    source_domain = models.CharField(max_length=128, null=True, blank=True)
    domains = ArrayField(
        models.CharField(max_length=128, null=True),
        null=True,
        blank=True,
        default=list
    )
