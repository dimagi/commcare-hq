import pickle

from django.conf import settings
from django_redis.serializers.pickle import PickleSerializer
from testil import eq


def test_highest_protocol():
    assert pickle.HIGHEST_PROTOCOL <= 5, """
        The highest pickle procol supported by Python at time of writing
        this test is 5. Support for newer protocols must be added or the
        default version used by libraries such as django_redis must be
        limited to 5 or less so pickles written by a newer Python can be
        read by an older Python after a downgrade.
    """


def test_pickle_5():
    eq(pickle.loads(b'\x80\x05\x89.'), False)


def test_dump_and_load_all_protocols():
    def test(protocol):
        eq(pickle.loads(pickle.dumps(False, protocol=protocol)), False)

    for protocol in range(1, pickle.HIGHEST_PROTOCOL + 1):
        yield test, protocol


def test_django_redis_protocol():
    # Override default pickle protocol to allow smoother Python upgrades.
    # Heroics like this will not be necessary once we have upgraded to a
    # version of django_redis that uses pickle.DEFAULT_PROTOCOL. See:
    # https://github.com/jazzband/django-redis/issues/547
    # https://github.com/jazzband/django-redis/pull/555
    #
    # This test may be removed after upgrading django_redis.
    # In the mean time, test for effective protocol override in settings.py
    pkl = PickleSerializer(settings.CACHES['default'].get("OPTIONS", {}))
    eq(pkl.dumps(False)[1], pickle.DEFAULT_PROTOCOL)
