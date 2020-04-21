import weakref
from base64 import urlsafe_b64encode, b64encode
from collections import deque
from datetime import datetime
from gzip import GzipFile
import hashlib
import os
import re
from io import RawIOBase

from jsonfield import JSONField

from corehq.blobs.exceptions import BadName, GzipStreamError

SAFENAME = re.compile("^[a-z0-9_./{}-]+$", re.IGNORECASE)


class NullJsonField(JSONField):
    """A JSONField that stores null when its value is empty

    Any value stored in this field will be discarded and replaced with
    the default if it evaluates to false during serialization.
    """

    def __init__(self, **kw):
        kw.setdefault("null", True)
        super(NullJsonField, self).__init__(**kw)
        assert self.null

    def get_db_prep_value(self, value, *args, **kw):
        if not value:
            value = None
        return super(NullJsonField, self).get_db_prep_value(value, *args, **kw)

    def to_python(self, value):
        value = super(NullJsonField, self).to_python(value)
        return self.get_default() if value is None else value

    def pre_init(self, value, obj):
        value = super(NullJsonField, self).pre_init(value, obj)
        return self.get_default() if value is None else value


class GzipStream:
    """Wrapper for a file like object that compresses the data as it is read

    Adapted from https://stackoverflow.com/a/31566082
    """
    CHUNK_SIZE = 4096

    def __init__(self, fileobj):
        self._input = fileobj
        self._buf = _IoBuffer()
        self._gzip = GzipFile(None, mode='wb', fileobj=self._buf)
        self._content_length = 0

    @property
    def content_length(self):
        """Size of uncompressed data

        Can only be accessed once stream has beenfully read.
        """
        if not self._gzip.closed or self._content_length is None:
            raise GzipStreamError("cannot read length before full stream")
        return self._content_length

    def read(self, size=-1):
        while size < 0 or len(self._buf) < size:
            chunk = self._input.read(self.CHUNK_SIZE)
            if not chunk:
                self._gzip.close()
                break
            self._content_length += len(chunk)
            self._gzip.write(chunk)
        return self._buf.read(size)

    def close(self):
        if not self._gzip.closed:
            self._content_length = None
        self._input.close()
        self._gzip.close()
        self._buf.close()


class _IoBuffer:
    def __init__(self):
        self.buffer = deque()
        self.size = 0

    def __len__(self):
        return self.size

    def write(self, data):
        self.buffer.append(data)
        self.size += len(data)

    def read(self, size=-1):
        if size < 0:
            size = self.size
        ret_list = []
        while size > 0 and self.buffer:
            s = self.buffer.popleft()
            size -= len(s)
            ret_list.append(s)
        if size < 0:
            ret_list[-1], remainder = ret_list[-1][:size], ret_list[-1][size:]
            self.buffer.appendleft(remainder)
        ret = b''.join(ret_list)
        self.size -= len(ret)
        return ret

    def flush(self):
        pass

    def close(self):
        self.buffer = None
        self.size = 0


class document_method(object):
    """Document method

    A document method is a twist between a static method and an instance
    method. It can be called as a normal instance method, in which case
    the first argument (`self`) is an instance of the method's class
    type, or it can be called like a static method:

        Document.method(obj, other, args)

    in which case the first argument is passed as `self` and need not
    be an instance of `Document`.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, owner):
        if obj is None:
            return self.func
        return self.func.__get__(obj, owner)


class classproperty(object):
    """https://stackoverflow.com/a/5192374/10840"""

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, owner):
        return self.func(owner)


def random_url_id(nbytes):
    """Get a random URL-safe ID string

    :param nbytes: Number of random bytes to include in the ID.
    :returns: A URL-safe string.
    """
    return urlsafe_b64encode(os.urandom(nbytes)).decode('ascii').rstrip('=')


def check_safe_key(key):
    """Perform some basic checks on a potential blob key

    This method makes a best-effort attempt to verify that the key is
    safe for all blob db backends. It will not necessarily detect all
    unsafe keys.

    :raises: BadName if key is unsafe.
    """
    if (key.startswith(("/", ".")) or
            "/../" in key or
            key.endswith("/..") or
            not SAFENAME.match(key)):
        raise BadName("unsafe key: %r" % key)


def _utcnow():
    return datetime.utcnow()


def get_content_md5(fileobj):
    """Get Content-MD5 value

    All content will be read from the current position to the end of the
    file. The file will be left open with its seek position at the end
    of the file.

    :param fileobj: A file-like object.
    :returns: RFC-1864-compliant Content-MD5 header value.
    """
    md5 = hashlib.md5()
    for chunk in iter(lambda: fileobj.read(1024 * 1024), b''):
        md5.update(chunk)
    return b64encode(md5.digest()).decode('ascii')


def set_max_connections(num_workers):
    """Set max connections for urllib3

    The default is 10. When using something like gevent to process
    multiple S3 connections conucurrently it is necessary to set max
    connections equal to the number of workers to avoid
    `WARNING Connection pool is full, discarding connection: ...`

    This must be called before `get_blob_db()` is called.

    See botocore.config.Config max_pool_connections
    https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
    """
    from django.conf import settings
    from corehq.blobs import _db

    def update_config(name):
        config = getattr(settings, name)["config"]
        config["max_pool_connections"] = num_workers

    assert not _db, "get_blob_db() has been called"
    for name in ["S3_BLOB_DB_SETTINGS", "OLD_S3_BLOB_DB_SETTINGS"]:
        if getattr(settings, name, False):
            update_config(name)


class BlobStream(RawIOBase):
    """Wrapper around the raw stream with additional properties for convenient access:

    * blob_key
    * content_length
    * compressed_length (will be None if blob is not compressed)
    """

    def __init__(self, stream, blob_db, blob_key, content_length, compressed_length):
        self._obj = stream
        self._blob_db = weakref.ref(blob_db)
        self.blob_key = blob_key
        self.content_length = content_length
        self.compressed_length = compressed_length

    def readable(self):
        return True

    def read(self, *args, **kw):
        return self._obj.read(*args, **kw)

    read1 = read

    def write(self, *args, **kw):
        raise IOError

    def tell(self):
        tell = getattr(self._obj, 'tell', None)
        if tell is not None:
            return tell()
        return self._obj._amount_read

    def seek(self, offset, from_what=os.SEEK_SET):
        if from_what != os.SEEK_SET:
            raise ValueError("seek mode not supported")
        pos = self.tell()
        if offset != pos:
            raise ValueError("seek not supported")
        return pos

    def close(self):
        self._obj.close()
        return super(BlobStream, self).close()

    def __getattr__(self, name):
        return getattr(self._obj, name)

    @property
    def blob_db(self):
        return self._blob_db()


def get_content_size(fileobj, chunks_sent):
    """
    :param fileobj: content object written to the backend
    :param chunks_sent: list of chunk sizes sent
    :return: tuple(uncompressed_size, compressed_size or None)
    """
    if isinstance(fileobj, GzipStream):
        return fileobj.content_length, sum(chunks_sent)

    return sum(chunks_sent), None
