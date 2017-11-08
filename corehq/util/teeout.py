from __future__ import absolute_import
import sys
import traceback
from contextlib import contextmanager


@contextmanager
def tee_output(stream):
    """Tee stdout and stderr to an additional (combined) output stream

    :param stream: File-like object open for writing.
    """
    real_stdout = sys.stdout
    real_stderr = sys.stderr
    sys.stdout = StreamTee(real_stdout, stream)
    sys.stderr = StreamTee(real_stderr, stream)
    try:
        yield
    except SystemExit:
        raise
    except:
        etype, exc, tb = sys.exc_info()
        stream.write("".join(traceback.format_exception(etype, exc, tb)))
        raise etype, exc, tb
    finally:
        sys.stdout = real_stdout
        sys.stderr = real_stderr


class StreamTee(object):

    def __init__(self, stream1, stream2):
        self.stream1 = stream1
        self.stream2 = stream2

    def __getattr__(self, name):
        value = getattr(self.stream1, name)
        if not callable(value):
            return value

        def func(*args, **kw):
            try:
                getattr(self.stream2, name)(*args, **kw)
            except Exception:
                pass
            return value(*args, **kw)
        func.__name__ = name
        return func
