import gevent
from testil import assert_raises

from ..util import UnhandledError, exit_on_error


def test_exit_on_error():
    @exit_on_error
    def fail():
        raise Exception("stop!")

    with assert_raises(UnhandledError, msg="stop!"):
        job = gevent.spawn(fail)
        gevent.wait([job])
