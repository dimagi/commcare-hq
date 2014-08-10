from couchdbkit.ext.django.schema import Document, BooleanProperty, StringProperty
from django.db import models
from casexml.apps.stock.models import DocDomainMapping


class MigrationCheckpoint(models.Model):
     domain = models.CharField(max_length=100)
     date = models.DateTimeField()


class ILSGatewayConfig(Document):
    enabled = BooleanProperty(default=False)
    domain = StringProperty()
    url = StringProperty()
    username = StringProperty()
    password = StringProperty()

    @classmethod
    def for_domain(cls, name):
        try:
            mapping = DocDomainMapping.objects.get(domain_name=name, doc_type='ILSGatewayConfig')
            return cls.get(docid=mapping.doc_id)
        except DocDomainMapping.DoesNotExist:
            return None

    @classmethod
    def get_all_configs(cls):
        mappings = DocDomainMapping.objects.filter(doc_type='ILSGatewayConfig')
        configs = [cls.get(docid=mapping.doc_id) for mapping in mappings]
        return configs

    @property
    def is_configured(self):
        return True if self.enabled and self.url and self.password and self.username else False

    def save(self, **params):
        super(ILSGatewayConfig, self).save(**params)
        try:
            DocDomainMapping.objects.get(doc_id=self._id,
                                         domain_name=self.domain,
                                         doc_type="ILSGatewayConfig")
        except DocDomainMapping.DoesNotExist:
            DocDomainMapping.objects.create(doc_id=self._id,
                                            domain_name=self.domain,
                                            doc_type='ILSGatewayConfig')