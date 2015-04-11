from dimagi.ext.couchdbkit import Document, BooleanProperty, StringProperty
from casexml.apps.stock.models import DocDomainMapping
from corehq.toggles import STOCK_AND_RECEIPT_SMS_HANDLER
from corehq.toggles import NAMESPACE_DOMAIN
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
        return [c.domain for c in filter(lambda config: config.enabled, configs)]

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


class AlertsSent(models.Model):
    create_date = models.DateTimeField(editable=False)
    alert_type = models.TextField()
    alert_text = models.TextField()
    supply_point_id = models.CharField(max_length=10)
