import datetime

from django.db import models
from django.contrib.postgres.fields import ArrayField

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.es import UserES
from corehq.apps.reports.analytics.esaccessors import (
    get_days_since_last_form_submission_for_user_id,
)
from corehq.apps.users.util import auto_deactivate_commcare_user
from corehq.util.dates import iso_string_to_datetime
from corehq.util.quickcache import quickcache


class EnterprisePermissions(models.Model):
    """
    Configuration for enterprise permissions, which causes users with accounts in the config's
    "source" domain to be automatically granted their same set of permissions in all domains
    controlled by the config.
    """
    account = models.OneToOneField(BillingAccount, null=False, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=False)
    source_domain = models.CharField(max_length=128, null=True, blank=True)
    domains = ArrayField(
        models.CharField(max_length=128, null=True),
        null=True,
        blank=True,
        default=list
    )

    @classmethod
    @quickcache(['domain'], timeout=7 * 24 * 60 * 60)
    def get_by_domain(cls, domain):
        """
        Get or create the configuration associated with the given domain's account.
        Note that the domain may be the source domain, one of the controlled domains,
        or another domain in the account that does not use enterprise permissions.
        """
        account = BillingAccount.get_account_by_domain(domain)
        try:
            return cls.objects.get(account=account)
        except cls.DoesNotExist:
            return cls(account=account)

    @classmethod
    @quickcache(['source_domain'], timeout=7 * 24 * 60 * 60)
    def get_domains(cls, source_domain):
        """
        Get a list of domains, if any, controlled by the given source domain.
        """
        try:
            config = cls.objects.get(is_enabled=True, source_domain=source_domain)
        except cls.DoesNotExist:
            return []
        return list(set(config.domains) - {config.source_domain})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for domain in self.account.get_domains():
            self.get_domains.clear(self.__class__, domain)
            self.get_by_domain.clear(self.__class__, domain)


class EnterpriseMobileWorkerSettings(models.Model):
    """
    Stores the configuration for auto-deactivating Mobile Workers for
    Enterprise projects
    """
    account = models.OneToOneField(BillingAccount, null=False, on_delete=models.CASCADE)
    enable_auto_deactivation = models.BooleanField(default=False)
    inactivity_period = models.IntegerField(default=90)
    allow_custom_deactivation = models.BooleanField(default=False)

    def deactivate_mobile_workers_by_inactivity(self, domain):
        user_query = UserES().domain(domain).mobile_users().is_active()
        user_data = user_query.source([
            '_id',
            'created_on',
        ]).run()
        for user in user_data.hits:
            inactive_days = get_days_since_last_form_submission_for_user_id(
                domain, user['_id']
            )
            if inactive_days == -1:
                delta = datetime.datetime.utcnow() - iso_string_to_datetime(user['created_on'])
                inactive_days = delta.days
            if inactive_days >= self.inactivity_period:
                auto_deactivate_commcare_user(user['_id'], domain)
