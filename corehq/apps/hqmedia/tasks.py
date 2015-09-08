import os
import tempfile
from wsgiref.util import FileWrapper
from celery.task import task
from celery.utils.log import get_task_logger
from django.conf import settings
import zipfile
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.util.files import file_extention_from_filename
from soil import DownloadBase
from django.utils.translation import ugettext as _
from soil.util import expose_file_download, expose_cached_download

logging = get_task_logger(__name__)

MULTIMEDIA_EXTENSIONS = ('.mp3', '.wav', '.jpg', '.png', '.gif', '.3gp', '.mp4', '.zip', )

@task
def process_bulk_upload_zip(processing_id, domain, app_id, username=None, share_media=False,
                            license_name=None, author=None, attribution_notes=None):
    """
        Responsible for processing the uploaded zip from Bulk Upload.
    """
    status = BulkMultimediaStatusCache.get(processing_id)

    if not status:
        # no download data available, abort
        return

    app = get_app(domain, app_id)

    status.in_celery = True
    status.save()

    uploaded_zip = status.get_upload_zip()
    if not uploaded_zip:
        return

    zipped_files = uploaded_zip.namelist()
    status.total_files = len(zipped_files)
    checked_paths = []

    try:
        for index, path in enumerate(zipped_files):
            status.update_progress(len(checked_paths))
            checked_paths.append(path)
            file_name = os.path.basename(path)
            try:
                data = uploaded_zip.read(path)
            except Exception as e:
                status.add_unmatched_path(path, _("Error reading file: %s" % e))
                continue

            media_class = CommCareMultimedia.get_class_by_data(data, filename=path)
            if not media_class:
                status.add_skipped_path(path, CommCareMultimedia.get_mime_type(data))
                continue

            app_paths = list(app.get_all_paths_of_type(media_class.__name__))
            app_paths_lower = [p.lower() for p in app_paths]
            form_path = media_class.get_form_path(path, lowercase=True)

            if not form_path in app_paths_lower:
                status.add_unmatched_path(path,
                                          _("Did not match any %s paths in application." % media_class.get_nice_name()))
                continue

            index_of_path = app_paths_lower.index(form_path)
            form_path = app_paths[index_of_path]  # this is the correct capitalization as specified in the form

            multimedia = media_class.get_by_data(data)
            if not multimedia:
                status.add_unmatched_path(path,
                                          _("Matching path found, but could not save the data to couch."))
                continue

            is_new = not form_path in app.multimedia_map.keys()
            is_updated = multimedia.attach_data(data,
                                                original_filename=file_name,
                                                username=username)

            if not is_updated and not getattr(multimedia, '_id'):
                status.add_unmatched_path(form_path,
                                          _("Matching path found, but didn't save new multimedia correctly."))
                continue

            if is_updated or is_new:
                multimedia.add_domain(domain, owner=True)
                if share_media:
                    multimedia.update_or_add_license(domain, type=license_name, author=author,
                                                     attribution_notes=attribution_notes)
                app.create_mapping(multimedia, form_path)

            media_info = multimedia.get_media_info(form_path, is_updated=is_updated, original_path=path)
            status.add_matched_path(media_class, media_info)

        status.update_progress(len(checked_paths))
    except Exception as e:
        status.mark_with_error(_("Error while processing zip: %s" % e))
    uploaded_zip.close()

    status.complete = True
    status.save()


@task
def build_application_zip(include_multimedia_files, include_index_files,
                            app, download_id, compress_zip=False, filename="commcare.zip"):
    from corehq.apps.hqmedia.views import iter_app_files
    
    DownloadBase.set_progress(build_application_zip, 0, 100)

    errors = []
    compression = zipfile.ZIP_DEFLATED if compress_zip else zipfile.ZIP_STORED

    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    if use_transfer:
        fpath = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, "{}{}{}{}".format(
            app._id,
            'mm' if include_multimedia_files else '',
            'ccz' if include_index_files else '',
            app.version,
        ))
    else:
        _, fpath = tempfile.mkstemp()

    if not (os.path.isfile(fpath) and use_transfer):  # Don't rebuild the file if it is already there
        files, errors = iter_app_files(app, include_multimedia_files, include_index_files)
        with open(fpath, 'wb') as tmp:
            with zipfile.ZipFile(tmp, "w") as z:
                for path, data in files:
                    # don't compress multimedia files
                    extension = os.path.splitext(path)[1]
                    file_compression = zipfile.ZIP_STORED if extension in MULTIMEDIA_EXTENSIONS else compression
                    z.writestr(path, data, file_compression)

    common_kwargs = dict(
        mimetype='application/zip' if compress_zip else 'application/x-zip-compressed',
        content_disposition='attachment; filename="{fname}"'.format(fname=filename),
        download_id=download_id,
    )
    if use_transfer:
        expose_file_download(
            fpath,
            use_transfer=use_transfer,
            **common_kwargs
        )
    else:
        expose_cached_download(
            FileWrapper(open(fpath)),
            expiry=(1 * 60 * 60),
            file_extension=file_extention_from_filename(filename),
            **common_kwargs
        )

    DownloadBase.set_progress(build_application_zip, 100, 100)
    return {
        "errors": errors,
    }
