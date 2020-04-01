from base64 import urlsafe_b64encode, b64encode
from collections import deque
from datetime import datetime
from gzip import GzipFile
import hashlib
import os
import re

from jsonfield import JSONField

from corehq.blobs.exceptions import BadName

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


# adapted from https://stackoverflow.com/a/31566082
class Buffer(object):
    def __init__(self):
        self.__buf = deque()
        self.__size = 0

    def __len__(self):
        return self.__size

    def write(self, data):
        self.__buf.append(data)
        self.__size += len(data)

    def read(self, size=-1):
        if size < 0: size = self.__size
        ret_list = []
        while size > 0 and len(self.__buf):
            s = self.__buf.popleft()
            size -= len(s)
            ret_list.append(s)
        if size < 0:
            ret_list[-1], remainder = ret_list[-1][:size], ret_list[-1][size:]
            self.__buf.appendleft(remainder)
        ret = b''.join(ret_list)
        self.__size -= len(ret)
        return ret

    def flush(self):
        pass

    def close(self):
        pass


class GzipCompressReadStream(object):
    CHUNK_SIZE = 4096

    def __init__(self, fileobj):
        self.__input = fileobj
        self.__buf = Buffer()
        self.__gzip = GzipFile(None, mode='wb', fileobj=self.__buf)

    def read(self, size=-1):
        while size < 0 or len(self.__buf) < size:
            chunk = self.__input.read(self.CHUNK_SIZE)
            if not chunk:
                self.__gzip.close()
                break
            self.__gzip.write(chunk)
        return self.__buf.read(size)

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
