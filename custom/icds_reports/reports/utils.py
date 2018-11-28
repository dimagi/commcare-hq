from __future__ import absolute_import
from __future__ import unicode_literals

import six


def get_color_with_green_positive(val):
    if isinstance(val, six.text_type):
        return 'red'
    return 'green' if val > 0 else 'red'


def get_color_with_red_positive(val):
    if isinstance(val, six.text_type):
        return 'green'
    return 'red' if val > 0 else 'green'
