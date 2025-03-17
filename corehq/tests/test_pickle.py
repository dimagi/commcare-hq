import pickle

import pytest
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


@pytest.mark.parametrize("protocol", range(1, pickle.HIGHEST_PROTOCOL + 1))
def test_dump_and_load_all_protocols(protocol):
    eq(pickle.loads(pickle.dumps(False, protocol=protocol)), False)
