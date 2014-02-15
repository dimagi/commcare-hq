import os
import tempfile
from dimagi.utils.decorators.memoized import memoized


def Temp(tmp):
    cls = PathTemp if isinstance(tmp, basestring) else StringIOTemp
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


class StringIOTemp(TempBase):
    def __init__(self, buffer):
        self.buffer = buffer

    @property
    def payload(self):
        return self.buffer.getvalue()

    @property
    @memoized
    def path(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as file:
            file.write(self.buffer.getvalue())
        return path

class ExportFiles(object):

    def __init__(self, file, checkpoint, format=None):
        self.file = Temp(file)
        self.checkpoint = checkpoint
        self.format = format
