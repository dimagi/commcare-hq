from decimal import Decimal

from django.utils.safestring import mark_safe
from django.utils.translation import get_language

from dimagi.ext.jsonobject import DictProperty, JsonObject, StringProperty

from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.transforms.custom.date import (
    days_elapsed_from_date,
    get_ethiopian_to_gregorian,
    get_gregorian_to_ethiopian,
    get_month_display,
)
from corehq.apps.userreports.transforms.custom.numeric import (
    get_short_decimal_display,
)
from corehq.apps.userreports.transforms.custom.users import (
    get_owner_display,
    get_user_display,
    get_user_without_domain_display,
)
from corehq.apps.userreports.util import localize


class Transform(JsonObject):
    """
    Transforms provide an interface to take in an input value and output something else.
    Useful if you need to transform data before saving or displaying it in some way.
    """
    type = StringProperty(required=True, choices=['custom'])


_CUSTOM_TRANSFORM_MAP = {
    'month_display': get_month_display,
    'days_elapsed_from_date': days_elapsed_from_date,
    'user_display': get_user_display,
    'owner_display': get_owner_display,
    'user_without_domain_display': get_user_without_domain_display,
    'short_decimal_display': get_short_decimal_display,
    'ethiopian_date_to_gregorian_date': get_ethiopian_to_gregorian,
    'gregorian_date_to_ethiopian_date': get_gregorian_to_ethiopian,
}


class CustomTransform(JsonObject):
    """
    Custom transforms provide an interface to a limited set of known, custom operations
    to transform data. Examples of custom transforms include things like looking up a username
    or owner name from the ID.
    """
    type = TypeProperty('custom')
    custom_type = StringProperty(required=True, choices=list(_CUSTOM_TRANSFORM_MAP))

    def get_transform_function(self):
        return _CUSTOM_TRANSFORM_MAP[self.custom_type]

    def transform(self, value):
        return self.get_transform_function()(value)


class DateFormatTransform(Transform):
    type = TypeProperty('date_format')
    format = StringProperty(required=True)

    def get_transform_function(self):

        def transform_function(value):
            try:
                return value.strftime(self.format)
            except Exception:
                return value

        return transform_function


class NumberFormatTransform(Transform):
    type = TypeProperty('number_format')
    format_string = StringProperty(required=True)

    def get_transform_function(self):

        def transform_function(value):
            try:
                if isinstance(value, str):
                    value = Decimal(value)
                return self.format_string.format(value)
            except Exception:
                return value

        return transform_function


class TranslationTransform(Transform):
    type = TypeProperty('translation')
    translations = DictProperty()
    # For mobile, the transform is a no-op and translation happens in the app
    mobile_or_web = StringProperty(default="web", choices=["mobile", "web"])

    def get_transform_function(self):
        if self.mobile_or_web == "mobile":  # Mobile translation happens later
            return lambda value: value

        def transform_function(value):
            if value not in self.translations:
                return value

            display = self.translations.get(value, {})
            language = get_language()
            return localize(display, language)

        return transform_function


class MultipleValueStringTranslationTransform(TranslationTransform):
    type = TypeProperty('multiple_value_string_translation')
    delimiter = StringProperty(required=True)

    def get_transform_function(self):
        delimiter = self.delimiter
        parent_transform_function = super(MultipleValueStringTranslationTransform, self).get_transform_function()

        def transform_function(values):
            values_list = values.split(delimiter)
            translated_values_list = []
            for value in values_list:
                translated_values_list.append(parent_transform_function(value))
            return delimiter.join(translated_values_list)

        return transform_function


class HyperLinkTransform(Transform):
    type = TypeProperty("hyperlink")
    link_text = StringProperty(required=True)

    def get_transform_function(self):
        link_text = mark_safe(self.link_text)
        
        def transform(value):
            link_url = mark_safe(value)
            return "<a href='{url}'>{text}</a>".format(url=link_url, text=link_text)

        return transform


class PrefixStringTransform(Transform):
    type = TypeProperty('prefix_string')
    prefix = StringProperty(required=True)

    def get_transform_function(self):

        def transform_function(value):
            return mark_safe(self.prefix) + value

        return transform_function


class NestedTransform(Transform):
    type = TypeProperty('nested')
    inner_expression = DictProperty(required=True)
    outer_expression = DictProperty(required=True)

    def get_transform_function(self):

        def transform(value):
            from corehq.apps.userreports.transforms.factory import TransformFactory
            inner_fn = TransformFactory.get_transform(self.inner_expression).get_transform_function()
            outer_fn = TransformFactory.get_transform(self.outer_expression).get_transform_function()
            return outer_fn(inner_fn(value))

        return transform


TRANSFORM_SPEC_MAP = {
    'custom': CustomTransform,
    'date_format': DateFormatTransform,
    'number_format': NumberFormatTransform,
    'translation': TranslationTransform,
    'multiple_value_string_translation': MultipleValueStringTranslationTransform,
    'hyperlink': HyperLinkTransform,
    'prefix_string': PrefixStringTransform,
    'nested': NestedTransform
}
