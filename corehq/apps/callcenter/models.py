from collections import namedtuple

import itertools
from jsonobject import JsonObject, BooleanProperty, SetProperty, StringProperty, ListProperty, ObjectProperty

from corehq.apps.callcenter import const

TypeRange = namedtuple('TypeRange', 'type, range_slug')


class BasicIndicator(JsonObject):
    enabled = BooleanProperty(default=False)
    date_ranges = SetProperty(unicode)


class TypedIndicator(BasicIndicator):
    type = StringProperty(unicode)


class ByTypeWithTotal(JsonObject):
    by_type = ListProperty(TypedIndicator)
    totals = ObjectProperty(BasicIndicator)
    all_types = BooleanProperty(default=False)

    @property
    def enabled(self):
        return self.totals.enabled or self.all_types or len(self.enabled_types) > 0

    @property
    def enabled_types(self):
        return [type_ for type_ in self.by_type if type_.enabled]

    def types_by_date_range(self):
        types_list = sorted([
            TypeRange(type_.type, date_range) for type_ in self.enabled_types
            for date_range in type_.date_ranges
        ], key=lambda x: x.range_slug)

        return {
            range_slug: {type_.type for type_ in group}
            for range_slug, group in itertools.groupby(types_list, lambda x: x.range_slug)
        }

    def get_or_add_for_type(self, type_):
        try:
            return [by_type for by_type in self.by_type if by_type.type == type_][0]
        except IndexError:
            indicator = TypedIndicator(enabled=True, type=type_)
            self.by_type.append(
                indicator
            )
            return indicator


class CallCenterIndicatorConfig(JsonObject):
    forms_submitted = ObjectProperty(BasicIndicator)
    cases_total = ObjectProperty(ByTypeWithTotal)
    cases_active = ObjectProperty(ByTypeWithTotal)
    cases_opened = ObjectProperty(ByTypeWithTotal)
    cases_closed = ObjectProperty(ByTypeWithTotal)

    legacy_forms_submitted = ObjectProperty(BasicIndicator)
    legacy_cases_total = ObjectProperty(BasicIndicator)
    legacy_cases_active = ObjectProperty(BasicIndicator)

    @classmethod
    def default_config(cls, include_legacy=True):
        def default_basic():
            return BasicIndicator(enabled=True, date_ranges=set(const.DATE_RANGES))

        def default_typed():
            return ByTypeWithTotal(totals=default_basic(), all_types=True)

        config = cls(
            forms_submitted=default_basic(),
            cases_total=default_typed(),
            cases_active=default_typed(),
            cases_opened=default_typed(),
            cases_closed=default_typed(),
        )

        if include_legacy:
            config.legacy_forms_submitted = default_basic()
            config.legacy_cases_total = default_basic()
            config.legacy_cases_active = default_basic()

        return config

    def set_indicator(self, parsed_indicator):
        if parsed_indicator.is_legacy:
            indicator = getattr(self, 'legacy_{}'.format(parsed_indicator.category))
            indicator.enabled = True
            if parsed_indicator.date_range:
                indicator.date_ranges.add(parsed_indicator.date_range)
        elif parsed_indicator.category == const.FORMS_SUBMITTED:
            self.forms_submitted.enabled = True
            if parsed_indicator.date_range:
                self.forms_submitted.date_ranges.add(parsed_indicator.date_range)
        else:
            indicator = getattr(self, parsed_indicator.category)
            if parsed_indicator.type:
                indicator = indicator.get_or_add_for_type(parsed_indicator.type)
            else:
                indicator = indicator.totals

            indicator.enabled = True
            if parsed_indicator.date_range:
                indicator.date_ranges.add(parsed_indicator.date_range)


from .signals import *
