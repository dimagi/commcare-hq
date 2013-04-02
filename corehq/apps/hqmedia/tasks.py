import StringIO
import os
from celery.task import task
from celery.utils.log import get_task_logger
from django.core.cache import cache
import zipfile
from corehq.apps.app_manager.models import get_app
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia
from soil import DownloadBase

logging = get_task_logger(__name__)

@task
def process_bulk_upload_zip(processing_id, domain, app_id, username=None, share_media=False,
                            license_name=None, author=None, attribution_notes=None, replace_existing=False):
    """
        Responsible for processing the uploaded zip from Bulk Upload.
    """

    from corehq.apps.hqmedia.views import ProcessBulkUploadView
    cache_key = ProcessBulkUploadView.get_cache_key(processing_id)
    upload_status_cache = cache.get(cache_key)

    if not upload_status_cache:
        # no download data available, abort
        return

    app = get_app(domain, app_id)

    upload_status_cache['in_celery'] = True
    cache.set(cache_key, upload_status_cache)

    def _mark_upload_with_error(error):
        upload_status_cache['complete'] = True
        upload_status_cache['errors'].append(error)
        cache.set(cache_key, upload_status_cache)

    try:
        saved_file = StringIO.StringIO()
        saved_ref = DownloadBase.get(processing_id)
        data = saved_ref.get_content()
        saved_file.write(data)
    except Exception as e:
        _mark_upload_with_error("Could not fetch cached bulk upload file. Error: %s." % e)
        return

    try:
        saved_file.seek(0)
        uploaded_zip = zipfile.ZipFile(saved_file)
    except Exception as e:
        _mark_upload_with_error("Error opening file as zip file: %s" % e)
        return

    if uploaded_zip.testzip():
        _mark_upload_with_error("Error encountered processing Zip File. File doesn't look valid.")
        return

    unmatched_files = []
    matched_files = {
        CommCareImage.__name__: [],
        CommCareAudio.__name__: [],
    }

    zipped_files = uploaded_zip.namelist()
    total_files = len(zipped_files)
    checked_paths = []

    upload_status_cache['total_files'] = total_files
    upload_status_cache['processed_files'] = 0

    def _add_unmatched(path, reason):
        unmatched_files.append({
            'path': path,
            'reason': reason,
        })
        checked_paths.append(path)

    def _update_progress():
        processed_files = len(checked_paths)
        upload_status_cache['processed_files'] = processed_files
        progress = int(100 * (float(processed_files) / float(total_files)))
        if progress > 100:
            logging.error("The progress of bulk upload exceeded 100 percent (%d). You "
                          "might want to check on this one, B." % progress)
        progress = min(progress, 100)  # always cap at 100
        upload_status_cache['progress'] = progress
        cache.set(cache_key, upload_status_cache)

    try:
        for index, path in enumerate(zipped_files):
            _update_progress()
            file_name = os.path.basename(path)
            try:
                data = uploaded_zip.read(path)
            except Exception as e:
                _add_unmatched(path, "Error reading file: %s" % e)
                continue

            media_class = CommCareMultimedia.get_class_by_data(data)
            if not media_class:
                _add_unmatched(path, "Did not process as a valid media file. Type: %s" %
                                     CommCareMultimedia.get_mime_type(data))
                continue

            app_paths = app.get_all_paths_of_type(media_class.__name__)
            form_path = media_class.get_form_path(path)

            if not form_path in app_paths:
                _add_unmatched(path, "Did not match any %s paths in application." % media_class.get_nice_name())
                continue

            multimedia = media_class.get_by_data(data)
            if not multimedia:
                _add_unmatched(path, "Matching path found, but could not save the data to couch.")
                continue

            is_updated = multimedia.attach_data(data, original_filename=file_name, username=username,
                                                replace_attachment=replace_existing)
            if not is_updated and not getattr(multimedia, '_id'):
                _add_unmatched(form_path, "Matching path found, but didn't save new multimedia correctly.")
                continue

            if is_updated:
                multimedia.add_domain(domain, owner=True)
                if share_media:
                    multimedia.update_or_add_license(domain, type=license_name, author=author,
                                                     attribution_notes=attribution_notes)
                app.create_mapping(multimedia, form_path)

            media_info = multimedia.get_media_info(form_path, is_updated=is_updated, original_path=path)
            matched_files[media_class.__name__].append(media_info)
            checked_paths.append(path)

        _update_progress()
        upload_status_cache["complete"] = True
        upload_status_cache["matched_files"] = matched_files
        upload_status_cache["unmatched_files"] = unmatched_files
        cache.set(cache_key, upload_status_cache)
    except Exception as e:
        _mark_upload_with_error("Error while processing zip: %s" % e)
    uploaded_zip.close()

