from couchdbkit.ext.django.schema import Document, BooleanProperty, StringProperty
from casexml.apps.stock.models import DocDomainMapping
from corehq.apps.users.models import CommCareUser
from corehq.toggles import STOCK_AND_RECEIPT_SMS_HANDLER
from custom.utils.utils import flat_field
from fluff.filters import CustomFilter

from corehq.toggles import NAMESPACE_DOMAIN
import fluff


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

        if self.enabled:
            STOCK_AND_RECEIPT_SMS_HANDLER.set(self.domain, True, NAMESPACE_DOMAIN)


class Numerator(fluff.Calculator):
    @fluff.null_emitter
    def numerator(self, doc):
        yield None


class EwsSmsUserFluff(fluff.IndicatorDocument):
    def user_data(property):
        return flat_field(lambda user: user.user_data.get(property))

    document_class = CommCareUser
    document_filter = CustomFilter(lambda user: user.is_active)
    domains = tuple(EWSGhanaConfig.get_all_enabled_domains())
    group_by = ('domain', )

    save_direct_to_sql = True

    name = flat_field(lambda user: user.name)

    numerator = Numerator()
    phone_number = flat_field(lambda user: user.phone_numbers[0] if user.phone_numbers else None)
    location_id = flat_field(lambda user: user.domain_membership.location_id if hasattr(
        user, 'domain_membership') else None)
    role = user_data('role')


EwsSmsUserFluffPillow = EwsSmsUserFluff.pillow()
