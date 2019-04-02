from __future__ import absolute_import
from __future__ import unicode_literals
import os
import tempfile
import six
from io import open

from corehq.util.python_compatibility import soft_assert_type_text


def Temp(tmp):
    if isinstance(tmp, six.string_types):
        soft_assert_type_text(tmp)
    cls = PathTemp if isinstance(tmp, six.string_types) else StringIOTemp
    return cls(tmp)


class TempBase(object):

    @property
    def file(self):
        return open(self.path, 'rb')


class PathTemp(TempBase):

    def __init__(self, path):
        self.path = path

    @property
    def payload(self):
        with open(self.path, 'rb') as f:
            return f.read()

    def delete(self):
        os.remove(self.path)


class StringIOTemp(TempBase):

    def __init__(self, buffer):
        self.buffer = buffer
        self._path = None

    @property
    def payload(self):
        return self.buffer.getvalue()

    @property
    def path(self):
        if self._path is None:
            fd, path = tempfile.mkstemp()
            with os.fdopen(fd, 'wb') as file:
                file.write(self.buffer.getvalue())
            self._path = path
        return self._path

    def delete(self):
        if self._path is not None:
            os.remove(self._path)


class ExportFiles(object):

    def __init__(self, file, checkpoint, format=None):
        self.file = Temp(file)
        self.checkpoint = checkpoint
        self.format = format

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file.delete()
