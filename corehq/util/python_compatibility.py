from __future__ import absolute_import
from __future__ import unicode_literals

import six
from django_redis.serializers.pickle import PickleSerializer

from corehq.util.soft_assert import soft_assert

try:
    import cPickle as pickle
except ImportError:
    import pickle


_soft_assert_type_text = soft_assert(
    to='{}@{}'.format('npellegrino', 'dimagi.com'),
    exponential_backoff=True,
)


# After PY3 migration: remove
def soft_assert_type_text(value):
    _soft_assert_type_text(isinstance(value, six.text_type), 'expected unicode, got: %s' % type(value))


class Py3PickleSerializer(PickleSerializer):
    """Load pickles in Python 3 that were serialized by Python 2

    This can be removed sometime after the codebase is running on Python
    3 and all pickles written by Python 2 have been removed from redis.
    """

    def loads(self, value):
        return pickle.loads(value, encoding="latin1", fix_imports=True)
