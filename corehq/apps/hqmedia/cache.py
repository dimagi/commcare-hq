import logging
from django.core.cache import cache
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio
from django.utils.translation import ugettext as _

class BaseMultimediaStatusCache(object):
    upload_type = None
    cache_expiry = 60 * 60 # defaults to one hour

    def __init__(self, processing_id):
        self.processing_id = processing_id
        self.in_celery = False
        self.complete = False
        self.progress = 0
        self.errors = []
        if self.upload_type is None:
            raise NotImplementedError("You need to specify an upload type.")

    def __str__(self):
        return "Status of process id %(processing_id)s: %(progress)d%%" % {
            'processing_id': self.processing_id,
            'progress': self.progress,
        }

    def save(self):
        cache.set(self.get_cache_key(self.processing_id), self, self.cache_expiry)

    def mark_with_error(self, error_str):
        self.complete = True
        self.errors.append(error_str)
        self.save()

    def get_response(self):
        """
            Modify the response you want to send back to the uploader as you want.
        """
        response = self.__dict__
        response.update({
            'type': self.upload_type,
        })
        return response

    @classmethod
    def get_cache_key(cls, processing_id):
        raise NotImplementedError("You need to specify a cache_key format for the status.")

    @classmethod
    def get(cls, processing_id):
        return cache.get(cls.get_cache_key(processing_id))


class BulkMultimediaStatusCache(BaseMultimediaStatusCache):
    upload_type = "zip"

    def __init__(self, processing_id):
        super(BulkMultimediaStatusCache, self).__init__(processing_id)
        self.unmatched_files = []
        self.matched_files = dict((m.__name__, []) for m in self.allowed_media)
        self.total_files = None
        self.processed_files = None

    @property
    def allowed_media(self):
        return [CommCareAudio, CommCareImage]

    def update_progress(self, num_files_processed):
        if self.total_files is None:
            raise ValueError("You need to set total_files before you can update progress.")
        self.processed_files = num_files_processed
        self.progress = int(100 * (float(self.processed_files) / float(self.total_files)))
        if self.progress >= 100:
            self.complete = True
        self.save()

    def add_unmatched_path(self, path, reason):
        self.unmatched_files.append({
            'path': path,
            'reason': reason,
        })

    def add_matched_path(self, media_class, media_info):
        if media_class.__name__ in self.matched_files:
            self.matched_files[media_class.__name__].append(media_info)
        else:
            self.add_unmatched_path(media_info['path'],
                                    _("Not a bulk-upload supported CommCareMedia type: %s" % media_class.__name__))

    @classmethod
    def get_cache_key(cls, processing_id):
        return "MMBULK_%s" % processing_id

