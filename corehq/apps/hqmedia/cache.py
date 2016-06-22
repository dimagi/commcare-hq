import StringIO
import zipfile
from django.core.cache import cache
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareVideo
from django.utils.translation import ugettext as _
from soil import DownloadBase


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
            Response that gets sent back to the upload controller.
        """
        return {
            'type': self.upload_type,
            'in_celery': self.in_celery,
            'complete': self.complete,
            'progress': self.progress,
            'errors': self.errors,
            'processing_id': self.processing_id,
        }

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
        self.skipped_files = []
        self.unmatched_files = []
        self.matched_files = dict((m.__name__, []) for m in self.allowed_media)
        self.total_files = None
        self.processed_files = None

    @property
    def allowed_media(self):
        return [CommCareAudio, CommCareImage, CommCareVideo]

    def get_response(self):
        response = super(BulkMultimediaStatusCache, self).get_response()
        response.update({
            'unmatched_files': self.unmatched_files,
            'matched_files': self.matched_files,
            'total_files': self.total_files,
            'processed_files': self.processed_files,
            'skipped_files': self.skipped_files,
        })
        return response

    def update_progress(self, num_files_processed):
        if self.total_files is None:
            raise ValueError("You need to set total_files before you can update progress.")
        self.processed_files = num_files_processed
        self.progress = int(100 * (float(self.processed_files) / float(self.total_files)))
        if self.progress >= 100:
            self.complete = True
        self.save()

    def add_skipped_path(self, path, mimetype):
        self.skipped_files.append({
            'path': path,
            'mimetype': mimetype,
        })

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

    def _get_upload_file(self):
        saved_file = StringIO.StringIO()
        try:
            saved_ref = DownloadBase.get(self.processing_id)
            data = saved_ref.get_content()
        except Exception as e:
            self.mark_with_error(_("Could not fetch cached bulk upload file. Error: %s." % e))
            return

        saved_file.write(data)
        saved_file.seek(0)
        return saved_file

    def get_upload_zip(self):
        saved_file = self._get_upload_file()

        try:
            uploaded_zip = zipfile.ZipFile(saved_file)
        except Exception as e:
            self.mark_with_error(_("Error opening file as zip file: %s" % e))
            return

        if uploaded_zip.testzip():
            self.mark_with_error(_("Error encountered processing Zip File. File doesn't look valid."))
            return

        return uploaded_zip

    @classmethod
    def get_cache_key(cls, processing_id):
        return "MMBULK_%s" % processing_id


class BulkMultimediaStatusCacheNfs(BulkMultimediaStatusCache):

    def __init__(self, processing_id, file_path):
        super(BulkMultimediaStatusCacheNfs, self).__init__(processing_id)
        self.file_path = file_path

    def _get_upload_file(self):
        return self.file_path
