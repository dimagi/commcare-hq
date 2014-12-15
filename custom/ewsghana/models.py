from couchdbkit.ext.django.schema import Document, BooleanProperty, StringProperty
from casexml.apps.stock.models import DocDomainMapping
from corehq.toggles import STOCK_AND_RECEIPT_SMS_HANDLER
from toggle.shortcuts import update_toggle_cache, namespaced_item
from toggle.models import Toggle
from corehq.toggles import NAMESPACE_DOMAIN


class EWSGhanaConfig(Document):
    enabled = BooleanProperty(default=False)
    domain = StringProperty()
    url = StringProperty(default="http://ewsghana.com/api/v0_1")
    username = StringProperty()
    password = StringProperty()

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
        toggle = Toggle.get(STOCK_AND_RECEIPT_SMS_HANDLER.slug)
        toggle_user_key = namespaced_item(self.domain, NAMESPACE_DOMAIN)

        if self.enabled and toggle_user_key not in toggle.enabled_users:
            toggle.enabled_users.append(toggle_user_key)
            toggle.save()
            update_toggle_cache(
                STOCK_AND_RECEIPT_SMS_HANDLER.slug,
                toggle_user_key, True
            )
