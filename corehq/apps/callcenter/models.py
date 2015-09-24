# Stub models file
from collections import namedtuple
import itertools
from django.conf import settings
from corehq.apps.callcenter.const import DATE_RANGES
from corehq.util.quickcache import skippable_quickcache
from dimagi.ext.couchdbkit import *

TypeRange = namedtuple('TypeRange', 'type, range_slug')


class BasicIndicator(DocumentSchema):
    active = BooleanProperty()
    date_ranges = StringListProperty()
    include_legacy = BooleanProperty()


class TypedIndicator(BasicIndicator):
    type = StringProperty()


class ByTypeIndicator(DocumentSchema):
    include_legacy = BooleanProperty()
    total = SchemaProperty(BasicIndicator)
    all_types = BooleanProperty()  # same date ranges as 'total'
    types = SchemaListProperty(TypedIndicator)

    @property
    def active(self):
        return self.total.active or self.all_types or any(type_.active for type_ in self.types)

    def types_by_date_range(self):
        types_list = sorted([
            TypeRange(type_.type, date_range) for type_ in self.types
            for date_range in type_.date_ranges
            if type_.active
        ], key=lambda x: x.range_slug)
        return {
            range_slug: {type_.type for type_ in group}
            for range_slug, group in itertools.groupby(types_list, lambda x: x.range_slug)
        }


class CallCenterIndicatorConfig(Document):
    domain = StringProperty()
    forms_submitted = SchemaProperty(BasicIndicator)
    cases_total = SchemaProperty(ByTypeIndicator)
    cases_active = SchemaProperty(ByTypeIndicator)
    cases_opened = SchemaProperty(ByTypeIndicator)
    cases_closed = SchemaProperty(ByTypeIndicator)

    @classmethod
    @skippable_quickcache(['domain'], lambda *_: settings.UNIT_TESTING)
    def for_domain(cls, domain):
        res = cls.view(
            "domain/docs",
            key=[domain, cls.__name__, None],
            reduce=False,
            include_docs=True).all()

        return res[0] if len(res) else cls.default_config(domain)

    @classmethod
    def default_config(cls, domain, include_legacy=True):
        def default_basic():
            return BasicIndicator(active=True, date_ranges=DATE_RANGES, include_legacy=include_legacy)

        def default_typed():
            return ByTypeIndicator(
                total=default_basic(),
                all_types=True,
                include_legacy=include_legacy
            )

        return cls(
            domain=domain,
            forms_submitted=default_basic(),
            cases_total=default_typed(),
            cases_active=default_typed(),
            cases_opened=default_typed(),
            cases_closed=default_typed(),
        )

    def save(self, **params):
        super(CallCenterIndicatorConfig, self).save(**params)
        CallCenterIndicatorConfig.for_domain.clear(self.__class__, self.domain)


from .signals import *
