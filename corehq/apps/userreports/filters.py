from django.utils.translation import ugettext as _
from corehq.apps.userreports.exceptions import BadSpecError
from fluff.filters import Filter


class ConfigurableFilter(Filter):
    # this currently has the exact same API as fluff.filters.Filter
    # but adds a function (from_spec)
    def filter(self, item):
        raise NotImplementedError()

    @classmethod
    def from_spec(cls, spec):
        raise NotImplementedError()


class PropertyMatchFilter(ConfigurableFilter):

    def __init__(self, property_name, property_value):
        self.property_name = property_name
        self.property_value = property_value

    def filter(self, item):
        try:
            return getattr(item, self.property_name) == self.property_value
        except AttributeError:
            return False

    @classmethod
    def from_spec(cls, spec):
        for key in ('property_name', 'property_value'):
            if not spec.get(key):
                raise BadSpecError(_('Property match filter spec must include valid a {0} field.'.format(key)))
        return cls(property_name=spec['property_name'], property_value=spec['property_value'])
