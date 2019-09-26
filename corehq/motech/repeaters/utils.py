from collections import OrderedDict

from dimagi.utils.modules import to_function

from corehq.motech.repeaters.const import REPEATER_CLASSES


def get_all_repeater_types():
    return OrderedDict([
        (to_function(cls, failhard=True).__name__, to_function(cls, failhard=True)) for cls in REPEATER_CLASSES
    ])
