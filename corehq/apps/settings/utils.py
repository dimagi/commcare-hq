import os
import tempfile
from contextlib import contextmanager


@contextmanager
def get_temp_file():
    fd, name = tempfile.mkstemp()
    yield fd, name
    try:
        os.close(fd)
    except OSError:  # The file has already been closed.
        pass
    try:
        os.unlink(name)
    except OSError:  # The file has already been deleted.
        pass
