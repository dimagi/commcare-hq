import StringIO
import os
from celery.task import task
from celery.utils.log import get_task_logger
from django.core.cache import cache
import zipfile
from corehq.apps.app_manager.models import get_app
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache
from corehq.apps.hqmedia.models import CommCareImage, CommCareAudio, CommCareMultimedia
from soil import DownloadBase
from django.utils.translation import ugettext as _

logging = get_task_logger(__name__)

@task
def process_bulk_upload_zip(processing_id, domain, app_id, username=None, share_media=False,
                            license_name=None, author=None, attribution_notes=None, replace_existing=False):
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

    try:
        saved_file = StringIO.StringIO()
        saved_ref = DownloadBase.get(processing_id)
        data = saved_ref.get_content()
        saved_file.write(data)
    except Exception as e:
        status.mark_with_error(_("Could not fetch cached bulk upload file. Error: %s." % e))
        return

    try:
        saved_file.seek(0)
        uploaded_zip = zipfile.ZipFile(saved_file)
    except Exception as e:
        status.mark_with_error(_("Error opening file as zip file: %s" % e))
        return

    if uploaded_zip.testzip():
        status.mark_with_error(_("Error encountered processing Zip File. File doesn't look valid."))
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

            media_class = CommCareMultimedia.get_class_by_data(data)  # most reliable way to verify the file

            if not media_class:
                media_class = CommCareMultimedia.get_class_by_filename(path)  # last resort
                if not media_class:
                    # skip these...
                    status.add_skipped_path(path, CommCareMultimedia.get_mime_type(data))
                    continue

            app_paths = app.get_all_paths_of_type(media_class.__name__)
            form_path = media_class.get_form_path(path)

            if not form_path in app_paths:
                status.add_unmatched_path(path,
                                          _("Did not match any %s paths in application." % media_class.get_nice_name()))
                continue

            multimedia = media_class.get_by_data(data)
            if not multimedia:
                status.add_unmatched_path(path,
                                          _("Matching path found, but could not save the data to couch."))
                continue

            is_updated = multimedia.attach_data(data, original_filename=file_name, username=username,
                                                replace_attachment=replace_existing)
            if not is_updated and not getattr(multimedia, '_id'):
                status.add_unmatched_path(form_path,
                                          _("Matching path found, but didn't save new multimedia correctly."))
                continue

            if is_updated:
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

