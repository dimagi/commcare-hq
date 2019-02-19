from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple

import itertools
from jsonobject import JsonObject, BooleanProperty, SetProperty, StringProperty, ListProperty, ObjectProperty

from corehq.apps.callcenter import const
import six

TypeRange = namedtuple('TypeRange', 'type, range_slug')


class BasicIndicator(JsonObject):
    enabled = BooleanProperty(default=False)
    date_ranges = SetProperty(six.text_type)


class TypedIndicator(BasicIndicator):
    type = StringProperty(six.text_type)


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

    legacy_forms_submitted = BooleanProperty(False)
    legacy_cases_total = BooleanProperty(False)
    legacy_cases_active = BooleanProperty(False)

    custom_form = ListProperty(TypedIndicator)

    def includes_legacy(self):
        return (
            self.legacy_forms_submitted or
            self.legacy_cases_total or
            self.legacy_cases_active
        )

    @classmethod
    def default_config(cls, domain_name=None, include_legacy=True):
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

        config.legacy_forms_submitted = include_legacy
        config.legacy_cases_total = include_legacy
        config.legacy_cases_active = include_legacy

        for slug in const.PER_DOMAIN_FORM_INDICATORS.get(domain_name, {}):
            for range in const.DATE_RANGES:
                config.custom_form.append(TypedIndicator(type=slug, date_range=range))

        return config

    def set_indicator(self, parsed_indicator):
        if parsed_indicator.is_legacy:
            indicator = getattr(self, parsed_indicator.category)
            setattr(self, 'legacy_{}'.format(parsed_indicator.category), True)
            if parsed_indicator.date_range:
                date_range = parsed_indicator.date_range
                if isinstance(indicator, ByTypeWithTotal):
                    indicator.totals.date_ranges.add(date_range)
                else:
                    indicator.date_ranges.add(date_range)
        elif parsed_indicator.category == const.CUSTOM_FORM:
            self.custom_form.append(
                TypedIndicator(
                    enabled=True,
                    date_range=parsed_indicator.date_range,
                    type=parsed_indicator.type
                )
            )
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
