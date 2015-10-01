from dimagi.ext.jsonobject import JsonObject, StringProperty
from corehq.apps.userreports.specs import TypeProperty
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
            except:
                return value

        return transform_function
