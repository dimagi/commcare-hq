import shutil
import uuid

from django.conf import settings

from soil import DownloadBase
from soil.util import expose_cached_download

from corehq.apps.hqmedia.cache import (
    BulkMultimediaStatusCache,
    BulkMultimediaStatusCacheNfs,
)
from corehq.util.files import file_extention_from_filename

MULTIMEDIA_PREFIX = "jr://file/"
IMAGE_MIMETYPES = ["image/jpeg", "image/gif", "image/png"]
AUDIO_MIMETYPES = ["audio/mpeg", "audio/mpeg3", "audio/wav", "audio/x-wav"]
ZIP_MIMETYPES = ["application/zip"]


def save_multimedia_upload(uploaded_file):
    """Save an uploaded multimedia ZIP file and return a processing_id.

    Handles both NFS-backed (temporary_file_path) and in-memory uploads.
    Creates a BulkMultimediaStatusCache entry for tracking.

    Returns a (processing_id, status) tuple. The processing_id is passed
    to process_bulk_upload_zip; the status object can be used to get the
    initial response without a cache re-fetch.
    """
    if hasattr(uploaded_file, 'temporary_file_path') and settings.SHARED_DRIVE_CONF.temp_dir:
        prefix = DownloadBase.new_id_prefix
        processing_id = prefix + uuid.uuid4().hex
        path = settings.SHARED_DRIVE_CONF.get_temp_file(suffix='.upload')
        shutil.move(uploaded_file.temporary_file_path(), path)
        status = BulkMultimediaStatusCacheNfs(processing_id, path)
        status.save()
    else:
        uploaded_file.seek(0)
        saved_file = expose_cached_download(
            uploaded_file.read(),
            expiry=BulkMultimediaStatusCache.cache_expiry,
            file_extension=file_extention_from_filename(uploaded_file.name),
        )
        processing_id = saved_file.download_id
        status = BulkMultimediaStatusCache(processing_id)
        status.save()

    return processing_id, status
