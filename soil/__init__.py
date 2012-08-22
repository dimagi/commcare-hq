import json
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.http import HttpResponse
import uuid

class DownloadBase(object):
    """
    A basic download object.
    """
    
    def __init__(self, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras=None, download_id=None):
        self.mimetype = mimetype
        self.content_disposition = content_disposition
        self.transfer_encoding = transfer_encoding
        self.extras = extras or {}
        self.download_id = download_id or uuid.uuid4().hex
        
    def get_content(self):
        raise NotImplemented("Use CachedDownload or FileDownload!")

    @classmethod
    def get(cls, download_id):
        return cache.get(download_id, None)

    def save(self, expiry=None):
        cache.set(self.download_id, self, expiry)

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

    def set_task(self, task):
        cache.set(self._task_key(), task.task_id)

    def _task_key(self):
        return self.download_id + ".task_id"
    @property
    def task_id(self):
        return cache.get(self._task_key(), None)

    @property
    def task(self):
        from celery.task.base import Task
        return Task.AsyncResult(self.task_id)

    def get_progress(self):
        if self.task.info is None:
            current = total = percent = None
        else:
            current = self.task.info.get('current')
            total = self.task.info.get('total')
            percent = current * 100./ total if total and current is not None else 0
        return {
            'current': current,
            'total': total,
            'percent': percent
        }

    @classmethod
    def set_progress(cls, task, current, total):
        task.update_state(state='PROGRESS', meta={'current': current, 'total': total})

class CachedDownload(DownloadBase):
    """
    Download that lives in the cache
    """
    
    def __init__(self, cacheindex, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras=None, download_id=None):
        super(CachedDownload, self).__init__(mimetype, content_disposition, 
                                             transfer_encoding, extras, download_id)
        self.cacheindex = cacheindex

    def get_content(self):
        return cache.get(self.cacheindex, None)

class FileDownload(DownloadBase):
    """
    Download that lives on the filesystem
    """
    
    def __init__(self, filename, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras=None, download_id=None):
        super(FileDownload, self).__init__(mimetype, content_disposition, 
                                             transfer_encoding, extras, download_id)
        self.filename = filename
        
    def get_content(self):
        with open(self.filename, 'rb') as f:
            return f.read()
        
