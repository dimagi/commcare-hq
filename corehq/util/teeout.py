import sys
import traceback
from contextlib import contextmanager


@contextmanager
def tee_output(stream, sys=sys):
    """Tee stdout and stderr to an additional (combined) output stream

    :param stream: File-like object open for writing or file path (str)
    or `None`. A value of `None` or empty string will create a no-op
    context manager.
    """
    if stream:
        filepath = stream if isinstance(stream, str) else None
        if filepath:
            stream = open(filepath, "a", buffering=1, encoding='utf-8')
        real_stdout = sys.stdout
        real_stderr = sys.stderr
        sys.stdout = StreamTee(real_stdout, stream)
        sys.stderr = StreamTee(real_stderr, stream)
    try:
        yield
    except SystemExit:
        raise
    except:  # noqa: E722  # Do not use bare `except`
        etype, exc, tb = sys.exc_info()
        if stream:
            stream.write("".join(traceback.format_exception(etype, exc, tb)))
        raise exc
    finally:
        if stream:
            if filepath:
                stream.close()
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
