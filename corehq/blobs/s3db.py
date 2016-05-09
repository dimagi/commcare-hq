from __future__ import absolute_import
import os
from contextlib import contextmanager
from threading import Lock

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.util import ClosingContextProxy

import boto3
from boto3.s3.transfer import S3Transfer, ReadFileChunk
from botocore.client import Config
from botocore.handlers import calculate_md5
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

from corehq.blobs.interface import AbstractBlobDB, SAFENAME

DEFAULT_S3_BUCKET = "blobdb"


class S3BlobDB(AbstractBlobDB):

    def __init__(self, config):
        kwargs = {}
        if "config" in config:
            kwargs["config"] = Config(**config["config"])
        self.db = boto3.resource(
            's3',
            endpoint_url=config.get("url"),
            aws_access_key_id=config.get("access_key", ""),
            aws_secret_access_key=config.get("secret_key", ""),
            **kwargs
        )
        self.s3_bucket_name = config.get("s3_bucket", DEFAULT_S3_BUCKET)
        self._s3_bucket_exists = False
        # https://github.com/boto/boto3/issues/259
        self.db.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)

    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        identifier = self.get_identifier(basename)
        path = self.get_path(identifier, bucket)
        self._s3_bucket(create=True)
        osutil = OpenFileOSUtils()
        transfer = S3Transfer(self.db.meta.client, osutil=osutil)
        transfer.upload_file(content, self.s3_bucket_name, path)
        content.seek(0)
        content_md5 = get_content_md5(content)
        content_length = osutil.get_file_size(content)
        return BlobInfo(identifier, content_length, "md5-" + content_md5)

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        with maybe_not_found(throw=NotFound(identifier, bucket)):
            resp = self._s3_bucket().Object(path).get()
        return ClosingContextProxy(resp["Body"])  # body stream

    def delete(self, *args, **kw):
        identifier, bucket = self.get_args_for_delete(*args, **kw)
        path = self.get_path(identifier, bucket)
        s3_bucket = self._s3_bucket()
        with maybe_not_found():
            if identifier is None:
                summaries = s3_bucket.objects.filter(Prefix=path + "/")
                pages = ([{"Key": o.key} for o in page]
                         for page in summaries.pages())
            else:
                pages = [[{"Key": path}]]
            success = True
            for objects in pages:
                resp = s3_bucket.delete_objects(Delete={"Objects": objects})
                if success:
                    deleted = set(d["Key"] for d in resp.get("Deleted", []))
                    success = all(o["Key"] in deleted for o in objects)
            return success
        return False

    def copy_blob(self, content, info, bucket):
        self._s3_bucket(create=True)
        path = self.get_path(info.identifier, bucket)
        osutil = OpenFileOSUtils()
        transfer = S3Transfer(self.db.meta.client, osutil=osutil)
        transfer.upload_file(content, self.s3_bucket_name, path)

    def _s3_bucket(self, create=False):
        if create and not self._s3_bucket_exists:
            try:
                self.db.meta.client.head_bucket(Bucket=self.s3_bucket_name)
            except ClientError as err:
                if not is_not_found(err):
                    raise
                self.db.create_bucket(Bucket=self.s3_bucket_name)
            self._s3_bucket_exists = True
        return self.db.Bucket(self.s3_bucket_name)

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET):
        if identifier is None:
            return safepath(bucket)
        return safejoin(bucket, identifier)


def safepath(path):
    if path.startswith(("/", ".")) or ".." in path or not SAFENAME.match(path):
        raise BadName(u"unsafe path name: %r" % path)
    return path


def safejoin(root, subpath):
    """Join root to subpath ensuring that the result is actually inside root
    """
    return safepath(root) + "/" + safepath(subpath)


def is_not_found(err, not_found_codes=["NoSuchKey", "NoSuchBucket", "404"]):
    return (err.response["Error"]["Code"] in not_found_codes or
        err.response.get("Errors", {}).get("Error", {}).get("Code") in not_found_codes)


def get_content_md5(content):
    params = {"body": content, "headers": {}}
    calculate_md5(params)
    return params["headers"]["Content-MD5"]


@contextmanager
def maybe_not_found(throw=None):
    try:
        yield
    except ClientError as err:
        if not is_not_found(err):
            raise
        if throw is not None:
            raise throw


class OpenFileOSUtils(object):

    def get_file_size(self, fileobj):
        if not hasattr(fileobj, 'fileno'):
            pos = fileobj.tell()
            try:
                fileobj.seek(0, os.SEEK_END)
                return fileobj.tell()
            finally:
                fileobj.seek(pos)
        return os.fstat(fileobj.fileno()).st_size

    def open_file_chunk_reader(self, fileobj, start_byte, size, callback):
        full_size = self.get_file_size(fileobj)
        return ReadOpenFileChunk(fileobj, start_byte, size, full_size,
                                 callback, enable_callback=False)

    def open(self, filename, mode):
        raise NotImplementedError

    def remove_file(self, filename):
        raise NotImplementedError

    def rename_file(self, current_filename, new_filename):
        raise NotImplementedError


class ReadOpenFileChunk(ReadFileChunk):
    """Wrapper for OpenFileChunk that implements ReadFileChunk interface
    """

    def __init__(self, fileobj, start_byte, chunk_size, full_file_size, *args, **kw):

        class FakeFile:

            def seek(self, pos):
                pass

        length = min(chunk_size, full_file_size - start_byte)
        self._chunk = OpenFileChunk(fileobj, start_byte, length)
        super(ReadOpenFileChunk, self).__init__(
            FakeFile(), start_byte, chunk_size, full_file_size, *args, **kw)
        assert self._size == length, (self._size, length)

    def __repr__(self):
        return ("<ReadOpenFileChunk {} offset={} length={}>".format(
            self._chunk.file,
            self._start_byte,
            self._size,
        ))

    def read(self, amount=None):
        data = self._chunk.read(amount)
        if self._callback is not None and self._callback_enabled:
            self._callback(len(data))
        return data

    def seek(self, where):
        old_pos = self._chunk.tell()
        self._chunk.seek(where)
        if self._callback is not None and self._callback_enabled:
            # To also rewind the callback() for an accurate progress report
            self._callback(where - old_pos)

    def tell(self):
        return self._chunk.tell()

    def close(self):
        self._chunk.close()
        self._chunk = None

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()


class OpenFileChunk(object):
    """A wrapper for reading from a file-like object from multiple threads

    Each thread reading from the file-like object should have its own
    private instance of this class.
    """

    init_lock = Lock()
    file_locks = {}

    def __init__(self, fileobj, start_byte, length):
        with self.init_lock:
            try:
                lock, refs = self.file_locks[fileobj]
            except KeyError:
                lock, refs = self.file_locks[fileobj] = (Lock(), set())
            refs.add(self)
        self.lock = lock
        self.file = fileobj
        self.start = self.offset = start_byte
        self.length = length

    def read(self, amount=None):
        if self.offset >= self.start + self.length:
            return b""
        with self.lock:
            pos = self.file.tell()
            self.file.seek(self.offset)

            if amount is None:
                amount = self.length
            amount = min(self.length - self.tell(), amount)
            read = self.file.read(amount)

            self.offset = self.file.tell()
            self.file.seek(pos)
            assert self.offset - self.start >= 0, (self.start, self.offset)
            assert self.offset <= self.start + self.length, \
                (self.start, self.length, self.offset)
        return read

    def seek(self, pos):
        assert pos >= 0, pos
        self.offset = self.start + pos

    def tell(self):
        return self.offset - self.start

    def close(self):
        if self.file is None:
            return
        try:
            with self.init_lock:
                lock, refs = self.file_locks[self.file]
                refs.remove(self)
                if not refs:
                    self.file_locks.pop(self.file)
        finally:
            self.file = None
            self.lock = None

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()
