from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
import re
import stat
import uuid
from tempfile import mkstemp
from wsgiref.util import FileWrapper

from django.conf import settings
from django.core import cache
from django.urls import reverse
from django.db import IntegrityError
from django.http import HttpResponse, StreamingHttpResponse

from django_transfer import TransferHttpResponse
from soil.progress import get_task_progress, get_multiple_task_progress
from corehq.blobs import DEFAULT_BUCKET, get_blob_db
import six


GLOBAL_RW = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH

SOIL_DEFAULT_CACHE = getattr(settings, 'SOIL_DEFAULT_CACHE', 'default')
if SOIL_DEFAULT_CACHE != 'default':
    assert SOIL_DEFAULT_CACHE in settings.CACHES, \
        "%s not found in settings.CACHES. Check you SOIL_DEFAULT_CACHE setting." % SOIL_DEFAULT_CACHE

CHUNK_SIZE = 8192


class DownloadBase(object):
    """
    A basic download object.
    """

    has_file = False

    def __init__(self, mimetype="text/plain",
                 content_disposition='attachment; filename="download.txt"',
                 transfer_encoding=None, extras=None, download_id=None,
                 cache_backend=SOIL_DEFAULT_CACHE, content_type=None,
                 suffix=None, message=None):
        self.content_type = content_type if content_type else mimetype
        self.content_disposition = self.clean_content_disposition(content_disposition)
        self.transfer_encoding = transfer_encoding
        self.extras = extras or {}
        self.download_id = download_id or uuid.uuid4().hex
        self.cache_backend = cache_backend
        # legacy default
        self.suffix = suffix or ''
        self.message = message

    def get_cache(self):
        return cache.caches[self.cache_backend]

    def get_content(self):
        raise NotImplemented("Use CachedDownload or FileDownload!")

    def get_filename(self):
        """
        Gets a filename of a file containing the content for this.
        """
        # some libraries like to work with files rather than content
        # so use this to force it be a file. FileDownload will override
        # this to avoid the duplicate storage.
        fd, filename = mkstemp(suffix=self.suffix)
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(self.get_content())
        return filename

    @classmethod
    def get(cls, download_id):
        if hasattr(settings, 'CACHES'):
            for backend in settings.CACHES.keys():
                res = cache.caches[backend].get(download_id, None)
                if res is not None:
                    return res
            return None
        else:
            return cache.cache.get(download_id, None)

    def save(self, expiry=None):
        self.get_cache().set(self.download_id, self, expiry)

    def clean_content_disposition(self, content_disposition):
        """
        http://manage.dimagi.com/default.asp?229983
        Sometimes filenames have characters in them which aren't allowed in
        headers and causes the download to fail.
        """
        if isinstance(content_disposition, six.string_types):
            return re.compile('[\r\n]').sub('', content_disposition)

        return content_disposition

    def toHttpResponse(self):
        response = HttpResponse(self.get_content(),
                content_type=self.content_type)
        if self.transfer_encoding is not None:
            response['Transfer-Encoding'] = self.transfer_encoding
        response['Content-Disposition'] = self.content_disposition
        for k, v in self.extras.items():
            response[k] = v
        return response

    def get_start_response(self):
        return HttpResponse(json.dumps({
            'download_id': self.download_id,
            'download_url': reverse('ajax_job_poll', kwargs={'download_id': self.download_id}),
            'message': self.message
        }))

    def __str__(self):
        return "content-type: %s, disposition: %s" % (self.content_type, self.content_disposition)

    def set_task(self, task, timeout=60 * 60 * 24):
        self.get_cache().set(self._task_key(), task.task_id, timeout)

    def _task_key(self):
        return self.download_id + ".task_id"

    @property
    def task_id(self):
        timeout = 60 * 60 * 24
        task_id = self.get_cache().get(self._task_key(), None)
        self.get_cache().set(self._task_key(), task_id, timeout)
        return task_id

    @property
    def task(self):
        from soil.util import get_task
        return get_task(self.task_id)

    def get_progress(self):
        task_progress = get_task_progress(self.task)
        return {
            'current': task_progress.current,
            'total': task_progress.total,
            'percent': task_progress.percent,
            'error': task_progress.error,
            'error_message': task_progress.error_message,
        }

    @classmethod
    def set_progress(cls, task, current, total):
        try:
            if task:
                task.update_state(state='PROGRESS', meta={'current': current, 'total': total})
        except (TypeError, NotImplementedError):
            pass
        except IntegrityError:
            # Not called in task context just pass
            pass

    @classmethod
    def create(cls, payload, **kwargs):
        """
        Create a Download object from a payload, plus any additional arguments
        to pass through to the constructor.
        """
        raise NotImplementedError("This should be overridden by subclasses!")


class MultipleTaskDownload(DownloadBase):
    """Download object for groups of tasks
    """

    @property
    def task(self):
        from celery.result import GroupResult
        result = GroupResult.restore(self.task_id)
        return result

    def set_task(self, task_group, timeout=60 * 60 * 24):
        task_group.save()
        self.get_cache().set(self._task_key(), task_group.id, timeout)

    def get_progress(self):
        return get_multiple_task_progress(self.task)


class CachedDownload(DownloadBase):
    """
    Download that lives in the cache
    """
    has_file = True

    def __init__(self, cacheindex, mimetype="text/plain",
                 content_disposition='attachment; filename="download.txt"',
                 transfer_encoding=None, extras=None, download_id=None,
                 cache_backend=SOIL_DEFAULT_CACHE, content_type=None,
                 suffix=None):
        super(CachedDownload, self).__init__(
            content_type if content_type else mimetype, content_disposition,
            transfer_encoding, extras, download_id, cache_backend,
            suffix=suffix)
        self.cacheindex = cacheindex

    def get_content(self):
        return self.get_cache().get(self.cacheindex, None)

    @classmethod
    def create(cls, payload, expiry, **kwargs):
        if isinstance(payload, FileWrapper):
            # I don't know what to do other than create a memory bottleneck here
            # can revisit when loading a whole file into memory becomes a
            # serious concern
            payload = ''.join(payload)
        download_id = str(uuid.uuid4())
        ret = cls(download_id, **kwargs)
        cache.caches[ret.cache_backend].set(download_id, payload, expiry)
        return ret


class FileDownload(DownloadBase):
    """
    Download that lives on the filesystem
    Uses django-transfer to get files stored on the external drive if use_transfer=True
    """
    has_file = True

    def __init__(self, filename, mimetype="text/plain",
                 content_disposition='attachment; filename="download.txt"',
                 transfer_encoding=None, extras=None, download_id=None, cache_backend=SOIL_DEFAULT_CACHE,
                 use_transfer=False, content_type=None):
        super(FileDownload, self).__init__(
                content_type if content_type else mimetype, content_disposition,
                transfer_encoding, extras, download_id, cache_backend)
        self.filename = filename
        self.use_transfer = use_transfer

    def get_content(self):
        with open(self.filename, 'rb') as f:
            return f.read()

    def get_filename(self):
        return self.filename

    def toHttpResponse(self):
        if self.use_transfer:
            response = TransferHttpResponse(self.filename,
                    content_type=self.content_type)
        else:
            response = StreamingHttpResponse(FileWrapper(open(self.filename), CHUNK_SIZE),
                                             content_type=self.content_type)

        response['Content-Length'] = os.path.getsize(self.filename)
        response['Content-Disposition'] = self.content_disposition
        if self.transfer_encoding is not None:
            response['Transfer-Encoding'] = self.transfer_encoding
        for k, v in self.extras.items():
            response[k] = v
        return response

    @classmethod
    def create(cls, path, **kwargs):
        """
        Create a FileDownload object from a payload, plus any
        additional arguments to pass through to the constructor.
        """
        return cls(filename=path, **kwargs)


class BlobDownload(DownloadBase):
    """
    Download that lives in the blobdb
    """
    has_file = True

    def __init__(self, identifier, mimetype="text/plain",
                 content_disposition='attachment; filename="download.txt"',
                 transfer_encoding=None, extras=None, download_id=None, cache_backend=SOIL_DEFAULT_CACHE,
                 content_type=None, bucket=DEFAULT_BUCKET):

        super(BlobDownload, self).__init__(
            mimetype=content_type if content_type else mimetype,
            content_disposition=content_disposition,
            transfer_encoding=transfer_encoding,
            extras=extras,
            download_id=download_id,
            cache_backend=cache_backend
        )
        self.identifier = identifier
        self.bucket = bucket

    def get_filename(self):
        return self.identifier

    def get_content(self):
        raise NotImplementedError

    def toHttpResponse(self):
        blob_db = get_blob_db()
        file_obj = blob_db.get(self.identifier, self.bucket)
        blob_size = blob_db.size(self.identifier, self.bucket)

        response = StreamingHttpResponse(
            FileWrapper(file_obj, CHUNK_SIZE),
            content_type=self.content_type
        )

        response['Content-Length'] = blob_size
        response['Content-Disposition'] = self.content_disposition
        for k, v in self.extras.items():
            response[k] = v
        return response

    @classmethod
    def create(cls, identifier, **kwargs):
        """
        Create a BlobDownload object from a payload, plus any
        additional arguments to pass through to the constructor.
        """
        return cls(identifier=identifier, **kwargs)
