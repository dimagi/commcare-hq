from django.core.files.uploadhandler import FileUploadHandler
from django.core.cache import cache

class HQMediaFileUploadHandler(FileUploadHandler):
    """ From django snippets: http://djangosnippets.org/snippets/678/
    """

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        self.content_length = content_length
        self.cache_handler = HQMediaUploadCacheHandler.handler_from_request(self.request)
        if self.cache_handler:
            self.cache_handler.defaults()
            if self.content_length > 200:
                self.cache_handler.data['length'] = self.content_length
                self.cache_handler.data['upload_aborted'] = False
            self.cache_handler.save()

    def new_file(self, field_name, file_name, content_type, content_length, charset=None):
        pass

    def receive_data_chunk(self, raw_data, start):
        if self.cache_handler:
            self.cache_handler.sync()
            self.cache_handler.data['uploaded'] += self.chunk_size
            self.cache_handler.save()
        return raw_data

    def file_complete(self, file_size):
        pass

    def upload_complete(self):
        if self.cache_handler:
            self.cache_handler.sync()
            self.cache_handler.data['upload_complete'] = True
            self.cache_handler.save()

class HQMediaCacheHandler(object):

    cache_key = None
    progress_id = None
    data = None
    X_PROGRESS_ID = 'X-Progress-ID'

    def __init__(self, progress_id, request):
        self.progress_id = progress_id
        self.cache_key = "%s_%s" % (request.META['REMOTE_ADDR'], progress_id)

    def put_data(self, data):
        if self.cache_key:
            cache.set(self.cache_key, data)

    def delete(self):
        if self.cache_key:
            cache.delete(self.cache_key)

    def sync(self):
        if self.cache_key:
            self.data = cache.get(self.cache_key)

    def save(self):
        self.put_data(self.data)

    def defaults(self):
        self.data = self.from_defaults()
        self.put_data(self.data)

    def from_defaults(self):
        return {}

    @classmethod
    def handler_from_request(cls, request):
        progress_id = ''
        if cls.X_PROGRESS_ID in request.GET:
            progress_id = request.GET[cls.X_PROGRESS_ID]
        elif cls.X_PROGRESS_ID in request.META:
            progress_id = request.META[cls.X_PROGRESS_ID]
        if progress_id:
            return cls(progress_id, request)
        return None

class HQMediaUploadCacheHandler(HQMediaCacheHandler):

    def from_defaults(self):
        return {'length': 1,
                'uploaded' : 0,
                'upload_complete': False,
                'upload_aborted': True,
                'processed_length': 100,
                'processed': 0,
                }

class HQMediaUploadSuccessCacheHandler(HQMediaCacheHandler):

    def __init__(self, progress_id, request):
        super(HQMediaUploadSuccessCacheHandler, self).__init__(progress_id, request)
        self.cache_key = "UploadSuccess_%s" % self.cache_key






