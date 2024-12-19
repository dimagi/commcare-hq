import datetime

from django.db import models
from django.contrib.postgres.fields import ArrayField

from dimagi.utils.chunked import chunked
from corehq import toggles
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.es import UserES, filters
from corehq.apps.users.util import bulk_auto_deactivate_commcare_users
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
    @quickcache(['domain'], timeout=7 * 24 * 60 * 60)
    def get_source_domain(cls, domain):
        """
        If the given domain is controlled by another domain via enterprise permissions,
        returns that controlling domain. Otherwise, returns None.
        """
        config = EnterprisePermissions.get_by_domain(domain)
        if config.is_enabled and domain in config.domains:
            return config.source_domain
        return None

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

    @classmethod
    @quickcache(['domain'], timeout=7 * 24 * 60 * 60)
    def is_source_domain(cls, domain):
        """
        Returns true if given domain is the source domain for an enabled configuration.
        """
        try:
            cls.objects.get(is_enabled=True, source_domain=domain)
        except cls.DoesNotExist:
            return False
        return True

    def save(self, *args, **kwargs):
        self.is_source_domain.clear(self.__class__, self.source_domain)
        for domain in self.account.get_domains():
            self.get_domains.clear(self.__class__, domain)
            self.get_source_domain.clear(self.__class__, domain)

        super().save(*args, **kwargs)
        self.is_source_domain.clear(self.__class__, self.source_domain)
        for domain in self.account.get_domains():
            self.get_domains.clear(self.__class__, domain)
            self.get_source_domain.clear(self.__class__, domain)


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
        date_of_inactivity = datetime.datetime.utcnow() - datetime.timedelta(
            days=self.inactivity_period
        )
        user_query = (
            UserES()
            .domain(domain)
            .mobile_users()
            .is_active()
            .created(lte=date_of_inactivity)
            .filter(
                filters.OR(
                    filters.date_range(
                        "reporting_metadata.last_submission_for_user.submission_date",
                        lte=date_of_inactivity
                    ),
                    filters.missing(
                        "reporting_metadata.last_submission_for_user.submission_date"
                    )
                )
            )
            .source(['_id'])
        )
        user_ids = [u['_id'] for u in user_query.run().hits]
        for chunked_ids in chunked(user_ids, 100):
            bulk_auto_deactivate_commcare_users(chunked_ids, domain)

    @classmethod
    @quickcache(['cls.__name__', 'domain'])
    def is_domain_using_custom_deactivation(cls, domain):
        if not toggles.AUTO_DEACTIVATE_MOBILE_WORKERS.enabled(
            domain, namespace=toggles.NAMESPACE_DOMAIN
        ):
            return False
        account = BillingAccount.get_account_by_domain(domain)
        try:
            emw_settings = cls.objects.get(account=account)
            return emw_settings.allow_custom_deactivation
        except cls.DoesNotExist:
            return False

    @classmethod
    def clear_domain_caches(cls, domain):
        cls.is_domain_using_custom_deactivation.clear(
            cls,
            domain
        )
