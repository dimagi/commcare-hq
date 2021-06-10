from django.db import models
from django.contrib.postgres.fields import ArrayField

from corehq.apps.accounting.models import BillingAccount


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

    @classmethod
    def get_by_domain(cls, domain):
        account = BillingAccount.get_account_by_domain(domain)
        try:
            return cls.objects.get(account=account)
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_domains(cls, source_domain):
        account = BillingAccount.get_account_by_domain(source_domain)
        try:
            config = cls.objects.get(account=account)
        except cls.DoesNotExist:
            return []
        if config.is_enabled and config.source_domain == source_domain:
            return list(set(config.domains) - {config.source_domain})
        return []
