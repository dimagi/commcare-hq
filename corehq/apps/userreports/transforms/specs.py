from decimal import Decimal
from django.utils.translation import get_language
from dimagi.ext.jsonobject import DictProperty, JsonObject, StringProperty
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.util import localize
from corehq.apps.userreports.transforms.custom.date import get_month_display, days_elapsed_from_date
from corehq.apps.userreports.transforms.custom.numeric import \
    get_short_decimal_display
from corehq.apps.userreports.transforms.custom.users import (
    get_user_display,
    get_owner_display,
    get_user_without_domain_display,
)


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
}


class CustomTransform(JsonObject):
    """
    Custom transforms provide an interface to a limited set of known, custom operations
    to transform data. Examples of custom transforms include things like looking up a username
    or owner name from the ID.
    """
    type = TypeProperty('custom')
    custom_type = StringProperty(required=True, choices=_CUSTOM_TRANSFORM_MAP.keys())

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
                if isinstance(value, basestring):
                    value = Decimal(value)
                return self.format_string.format(value)
            except Exception:
                return value

        return transform_function


class TranslationTransform(Transform):
    """
    Lets you map slugs to display strings, and/or translate them

    Simple mapping
        {
            "type": "translation",
            "translations": {
                "#0000FF": "Blue",
                "#800080": "Purple"
            }
        }

    Translated mapping
        {
            "type": "translation",
            "translations": {
                "#0000FF": {
                    "en": "Blue",
                    "es": "Azul",
                },
                "#800080": {
                    "en": "Purple",
                    "es": "Morado",
                }
            }
        }
    """
    type = TypeProperty('translation')
    translations = DictProperty()
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
