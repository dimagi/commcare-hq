from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

from django.conf import settings

from dimagi.utils.modules import to_function


def get_all_repeater_types():
    return OrderedDict([
        (to_function(cls, failhard=True).__name__, to_function(cls, failhard=True)) for cls in settings.REPEATERS
    ])
