from __future__ import absolute_import
from __future__ import unicode_literals

import six

from corehq.util.soft_assert import soft_assert

_soft_assert_type_text = soft_assert(
    to='{}@{}'.format('npellegrino', 'dimagi.com'),
    exponential_backoff=True,
)


# After PY3 migration: remove
def soft_assert_type_text(value):
    return
    _soft_assert_type_text(isinstance(value, six.text_type), 'expected unicode, got: %s' % type(value))
