# Stub models file
from collections import namedtuple
import itertools
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


class ByTypeIndicator(BasicIndicator):
    total = SchemaProperty(BasicIndicator)
    all_types = BooleanProperty()  # same date ranges as 'total'
    types = SchemaListProperty(TypedIndicator)

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
    @skippable_quickcache(['domain'], skip_arg='skip_cache')
    def for_domain(cls, domain, skip_cache=False):
        res = cls.view(
            "domain/docs",
            key=[domain, cls.__name__, None],
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap)

        return res[0] if len(res) else cls.default_config(domain)

    @classmethod
    def default_config(cls, domain, include_legacy=True):
        def default_basic():
            return BasicIndicator(active=True, date_ranges=DATE_RANGES, include_legacy=include_legacy)

        def default_typed():
            return ByTypeIndicator(
                active=True,
                date_ranges=DATE_RANGES,
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


from .signals import *
