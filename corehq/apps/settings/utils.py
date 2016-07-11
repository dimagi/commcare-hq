import os
import tempfile
from contextlib import contextmanager


@contextmanager
def get_temp_file():
    fd, name = tempfile.mkstemp()
    yield fd, name
    os.close(fd)
    os.unlink(name)
