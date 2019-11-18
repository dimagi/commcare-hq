import pickle

from django_redis.serializers.pickle import PickleSerializer


class Py3PickleSerializer(PickleSerializer):
    """Load pickles in Python 3 that were serialized by Python 2

    This can be removed sometime after the codebase is running on Python
    3 and all pickles written by Python 2 have been removed from redis.
    """

    def loads(self, value):
        return pickle.loads(value, encoding="latin1", fix_imports=True)
