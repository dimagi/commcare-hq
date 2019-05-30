from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import attr
import six
from django.utils.translation import ugettext_lazy as _

UGETTEXT_LAZY_TYPE = type(_(""))


@attr.s
class LimitType(object):
    name = attr.ib(validator=attr.validators.instance_of(six.string_types))
    default = attr.ib(validator=attr.validators.instance_of(int))
    unit = attr.ib(validator=attr.validators.instance_of(six.string_types))
    description = attr.ib(validator=attr.validators.instance_of(UGETTEXT_LAZY_TYPE))
    descriptions_of_impact = attr.ib(validator=attr.validators.instance_of(list))
    tags = attr.ib(validator=attr.validators.instance_of(set))

    @unit.validator
    def in_unit_whitelist(self, attribute, value):
        from .limits import UNITS
        if value not in UNITS:
            raise ValueError('must be one of: {}'.format(', '.join(UNITS)))

    @tags.validator
    def in_tags_whitelist(self, attribute, value):
        from .limits import TAGS
        bad_values = value - TAGS
        if bad_values:
            raise ValueError('bad tags ({}) must be one of: {}'
                             .format(', '.join(bad_values), ', '.join(TAGS)))

    @descriptions_of_impact.validator
    def is_list_of_ugettext_laxy_strings(self, attribute, value):
        has_bad_value = any(True for string in value
                            if not isinstance(string, UGETTEXT_LAZY_TYPE))
        if has_bad_value:
            raise ValueError('must be list of ugettext_lazy strings')
