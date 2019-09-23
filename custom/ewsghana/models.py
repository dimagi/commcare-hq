from django.dispatch import receiver
from corehq.apps.domain.models import Domain
from corehq.apps.domain.signals import commcare_domain_pre_delete
from corehq.apps.locations.models import SQLLocation, get_location
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.users.models import WebUser
from dimagi.ext.couchdbkit import Document, BooleanProperty, StringProperty
from casexml.apps.stock.models import DocDomainMapping
from corehq.toggles import STOCK_AND_RECEIPT_SMS_HANDLER, NAMESPACE_DOMAIN
from django.db import models


class EWSGhanaConfig(Document):
    enabled = BooleanProperty(default=False)
    domain = StringProperty()
    url = StringProperty(default="http://ewsghana.com/api/v0_1")
    username = StringProperty()
    password = StringProperty()
    steady_sync = BooleanProperty(default=False)
    all_stock_data = BooleanProperty(default=False)

    @classmethod
    def for_domain(cls, name):
        try:
            mapping = DocDomainMapping.objects.get(domain_name=name, doc_type='EWSGhanaConfig')
            return cls.get(docid=mapping.doc_id)
        except DocDomainMapping.DoesNotExist:
            return None

    @classmethod
    def get_all_configs(cls):
        mappings = DocDomainMapping.objects.filter(doc_type='EWSGhanaConfig')
        configs = [cls.get(docid=mapping.doc_id) for mapping in mappings]
        return configs

    @classmethod
    def get_all_steady_sync_configs(cls):
        return [
            config for config in cls.get_all_configs()
            if config.steady_sync
        ]

    @classmethod
    def get_all_enabled_domains(cls):
        configs = cls.get_all_configs()
        return [c.domain for c in [config for config in configs if config.enabled]]

    @property
    def is_configured(self):
        return True if self.enabled and self.url and self.password and self.username else False

    def save(self, **params):
        super(EWSGhanaConfig, self).save(**params)

        self.update_toggle()

        try:
            DocDomainMapping.objects.get(doc_id=self._id,
                                         domain_name=self.domain,
                                         doc_type="EWSGhanaConfig")
        except DocDomainMapping.DoesNotExist:
            DocDomainMapping.objects.create(doc_id=self._id,
                                            domain_name=self.domain,
                                            doc_type='EWSGhanaConfig')

    def update_toggle(self):
        """
        This turns on the special stock handler when EWS is enabled.
        """

        if self.enabled:
            STOCK_AND_RECEIPT_SMS_HANDLER.set(self.domain, True, NAMESPACE_DOMAIN)

    class Meta(object):
        app_label = 'ewsghana'


class FacilityInCharge(models.Model):
    user_id = models.CharField(max_length=128, db_index=True)
    location = models.ForeignKey(SQLLocation, on_delete=models.PROTECT)

    class Meta(object):
        app_label = 'ewsghana'


class EWSExtension(models.Model):
    user_id = models.CharField(max_length=128, db_index=True)
    domain = models.CharField(max_length=128)
    location_id = models.CharField(max_length=128, null=True, db_index=True)
    sms_notifications = models.BooleanField(default=False)

    @property
    def supply_point(self):
        if not self.location_id:
            return
        return get_location(self.location_id).linked_supply_point()

    @property
    def web_user(self):
        return WebUser.get(self.user_id)

    @property
    def verified_number(self):
        return PhoneNumber.get_two_way_number(self.phone_number)

    @property
    def domain_object(self):
        return Domain.get_by_name(self.domain)

    class Meta(object):
        app_label = 'ewsghana'


class SQLNotification(models.Model):
    domain = models.CharField(max_length=128)
    user_id = models.CharField(max_length=128)
    type = models.CharField(max_length=128)
    week = models.IntegerField()
    year = models.IntegerField()

    class Meta(object):
        app_label = 'ewsghana'


@receiver(commcare_domain_pre_delete)
def domain_pre_delete_receiver(domain, **kwargs):
    from corehq.apps.domain.deletion import ModelDeletion
    return [
        ModelDeletion('ewsghana', 'FacilityInCharge', 'location__domain'),
        ModelDeletion('ewsghana', 'EWSExtension', 'domain')
    ]
