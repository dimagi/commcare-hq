import json
import logging
from django.core import cache
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponse
import uuid
from django.conf import settings
import tempfile
import os
import stat
from tempfile import mkstemp

GLOBAL_RW = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH

SOIL_DEFAULT_CACHE = getattr(settings, 'SOIL_DEFAULT_CACHE', 'default')
if SOIL_DEFAULT_CACHE != 'default':
    assert SOIL_DEFAULT_CACHE in settings.CACHES, \
        "%s not found in settings.CACHES. Check you SOIL_DEFAULT_CACHE setting." % SOIL_DEFAULT_CACHE


class DownloadBase(object):
    """
    A basic download object.
    """
    
    def __init__(self, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras=None, download_id=None, 
                 cache_backend=SOIL_DEFAULT_CACHE):
        self.mimetype = mimetype
        self.content_disposition = content_disposition
        self.transfer_encoding = transfer_encoding
        self.extras = extras or {}
        self.download_id = download_id or uuid.uuid4().hex
        self.cache_backend = cache_backend


    def get_cache(self):
        return cache.get_cache(self.cache_backend)

    def get_content(self):
        raise NotImplemented("Use CachedDownload or FileDownload!")

    def get_filename(self):
        """
        Gets a filename of a file containing the content for this.
        """
        # some libraries like to work with files rather than content
        # so use this to force it be a file. FileDownload will override
        # this to avoid the duplicate storage.
        fd, filename = mkstemp(suffix='.xls')
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(self.get_content())
        return filename

    @classmethod
    def get(cls, download_id):
        if hasattr(settings, 'CACHES'):
            for backend in settings.CACHES.keys():
                res = cache.get_cache(backend).get(download_id, None)
                if res is not None:
                    return res
            return None
        else:
            return cache.cache.get(download_id, None)


    def save(self, expiry=None):
        self.get_cache().set(self.download_id, self, expiry)

    def toHttpResponse(self):
        response = HttpResponse(self.get_content(), mimetype=self.mimetype)
        if self.transfer_encoding is not None:
            response['Transfer-Encoding'] = self.transfer_encoding
        response['Content-Disposition'] = self.content_disposition
        for k,v in self.extras.items():
            response[k] = v
        return response

    def get_start_response(self):
        return HttpResponse(json.dumps({
            'download_id': self.download_id,
            'download_url': reverse('ajax_job_poll', kwargs={'download_id': self.download_id})
        }))

    def __str__(self):
        return "content-type: %s, disposition: %s" % (self.mimetype, self.content_disposition)

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
        from celery.task.base import Task
        return Task.AsyncResult(self.task_id)

    def get_progress(self):
        try:
            info = self.task.info
        except (TypeError, NotImplementedError):
            current = total = percent = None
            logging.exception("No celery result backend?")
        else:
            if info is None:
                current = total = percent = None
            else:
                current = info.get('current')
                total = info.get('total')
                percent = current * 100./ total if total and current is not None else 0
        return {
            'current': current,
            'total': total,
            'percent': percent
        }

    @classmethod
    def set_progress(cls, task, current, total):
        try:
            if task:
                task.update_state(state='PROGRESS', meta={'current': current, 'total': total})
        except (TypeError, NotImplementedError):
            pass
    
    @classmethod
    def create(cls, payload, **kwargs):
        """
        Create a Download object from a payload, plus any additional arguments 
        to pass through to the constructor.
        """
        raise NotImplementedError("This should be overridden by subclasses!")

class CachedDownload(DownloadBase):
    """
    Download that lives in the cache
    """
    
    def __init__(self, cacheindex, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras=None, download_id=None, 
                 cache_backend=SOIL_DEFAULT_CACHE):
        super(CachedDownload, self).__init__(mimetype, content_disposition, 
                                             transfer_encoding, extras, download_id, cache_backend)
        self.cacheindex = cacheindex

    def get_content(self):
        return self.get_cache().get(self.cacheindex, None)
    
    @classmethod
    def create(cls, payload, expiry, **kwargs):
        if isinstance(payload, FileWrapper):
            # I don't know of a way to stream to cache backend
            # so it should fail hard and force the caller to unwrap rather than
            # silently create a memory bottleneck here
            raise ValueError("CachedDownload does not support a FileWrapper instance as a payload")
        download_id = uuid.uuid4().hex
        ret = cls(download_id, **kwargs)
        cache.get_cache(ret.cache_backend).set(download_id, payload, expiry)
        return ret

class FileDownload(DownloadBase):
    """
    Download that lives on the filesystem
    """
    
    def __init__(self, filename, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras=None, download_id=None, cache_backend='default'):
        super(FileDownload, self).__init__(mimetype, content_disposition, 
                                             transfer_encoding, extras, download_id, cache_backend)
        self.filename = filename
    
    def get_content(self):
        with open(self.filename, 'rb') as f:
            return f.read()
        
    def get_filename(self):
        return self.filename

    @classmethod
    def create(cls, payload, expiry, **kwargs):
        """
        Create a FileDownload object from a payload, plus any 
        additional arguments to pass through to the constructor.
        """
        fd, path = tempfile.mkstemp()
        os.chmod(path, GLOBAL_RW)
        with os.fdopen(fd, "wb") as f:
            if isinstance(payload, FileWrapper):
                for chunk in payload:
                    f.write(chunk)
            else:
                f.write(payload)
        return cls(filename=path, **kwargs)