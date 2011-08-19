from django.core.cache import cache
from django.http import HttpResponse

class DownloadBase(object):
    """
    A basic download object.
    """
    
    def __init__(self, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding=None, extras={}):
        self.mimetype = mimetype
        self.content_disposition = content_disposition
        self.transfer_encoding = transfer_encoding
        self.extras = {}
        
    def get_content(self):
        raise NotImplemented("Use CachedDownload or FileDownload!")
    
    def toHttpResponse(self):
        response = HttpResponse(self.get_content(), mimetype=self.mimetype)
        if self.transfer_encoding is not None:
            response['Transfer-Encoding'] = self.transfer_encoding
        response['Content-Disposition'] = self.content_disposition
        for k,v in self.extras.items():
            response[k] = v
        return response
    
    def __str__(self):
        return "content-type: %s, disposition: %s" % (self.mimetype, self.content_disposition)

class CachedDownload(DownloadBase):
    """
    Download that lives in the cache
    """
    
    def __init__(self, cacheindex, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding="chunked", extras={}):
        super(CachedDownload, self).__init__(mimetype, content_disposition, 
                                             transfer_encoding, extras)
        self.cacheindex = cacheindex
        
    def get_content(self):
        return cache.get(self.cacheindex, None)

class FileDownload(DownloadBase):
    """
    Download that lives on the filesystem
    """
    
    def __init__(self, filename, mimetype="text/plain", 
                 content_disposition="attachment; filename=download.txt", 
                 transfer_encoding="chunked", extras={}):
        super(CachedDownload, self).__init__(mimetype, content_disposition, 
                                             transfer_encoding, extras)
        self.filename = filename
        
    def get_content(self):
        with open(self.filename, 'rb') as f:
            return f.read()
        
