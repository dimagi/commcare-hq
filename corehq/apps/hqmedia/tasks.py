import itertools
import json
import os
import re
import tempfile
import zipfile
from wsgiref.util import FileWrapper

from django.conf import settings
from django.utils.translation import gettext as _

from celery.utils.log import get_task_logger

from dimagi.utils.logging import notify_exception
from soil import DownloadBase
from soil.util import expose_cached_download, expose_file_download

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.celery import task
from corehq.apps.hqmedia.cache import BulkMultimediaStatusCache
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.util.files import file_extention_from_filename

logging = get_task_logger(__name__)

MULTIMEDIA_EXTENSIONS = ('.mp3', '.wav', '.jpg', '.png', '.gif', '.3gp', '.mp4', '.zip', )


@task(serializer='pickle')
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
        save_app = False
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

            is_new = form_path not in app.multimedia_map
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
                save_app = True
                app.create_mapping(multimedia, form_path, save=False)

            media_info = multimedia.get_media_info(form_path, is_updated=is_updated, original_path=path)
            status.add_matched_path(media_class, media_info)

        if save_app:
            app.save()
        status.update_progress(len(checked_paths))
    except Exception as e:
        status.mark_with_error(_("Error while processing zip: %s" % e))
    uploaded_zip.close()

    status.complete = True
    status.save()


@task(serializer='pickle')
def build_application_zip(include_multimedia_files, include_index_files, domain, app_id,
                          download_id, build_profile_id=None, compress_zip=False, filename="commcare.zip",
                          download_targeted_version=False):
    DownloadBase.set_progress(build_application_zip, 0, 100)
    app = get_app(domain, app_id)
    fpath = create_files_for_ccz(
        app,
        build_profile_id,
        include_multimedia_files,
        include_index_files,
        download_id,
        compress_zip,
        filename,
        download_targeted_version,
        task=build_application_zip,
    )
    DownloadBase.set_progress(build_application_zip, 100, 100)


def _get_file_path(app, include_multimedia_files, include_index_files, build_profile_id,
                   download_targeted_version):
    if settings.SHARED_DRIVE_CONF.transfer_enabled:

        fpath = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, "{}{}{}{}{}".format(
            app._id,
            'mm' if include_multimedia_files else '',
            'ccz' if include_index_files else '',
            app.version,
            build_profile_id
        ))
        if download_targeted_version:
            fpath += '-targeted'
    else:
        dummy, fpath = tempfile.mkstemp()
        os.close(dummy)
    return fpath


def _build_ccz_files(build, build_profile_id, include_multimedia_files, include_index_files,
                     download_id, compress_zip, filename, download_targeted_version):
    from corehq.apps.hqmedia.views import iter_app_files
    files, errors, file_count = iter_app_files(
        build, include_multimedia_files, include_index_files, build_profile_id,
        download_targeted_version=download_targeted_version,
    )

    if toggles.CAUTIOUS_MULTIMEDIA.enabled(build.domain):
        manifest = json.dumps({
            'include_multimedia_files': include_multimedia_files,
            'include_index_files': include_index_files,
            'download_id': download_id,
            'build_profile_id': build_profile_id,
            'compress_zip': compress_zip,
            'filename': filename,
            'download_targeted_version': download_targeted_version,
        }, indent=4)
        manifest_filename = '{} - {} - v{} manifest.json'.format(
            build.domain,
            build.name,
            build.version,
        )
        files = itertools.chain(files, [(manifest_filename, manifest)])
    return files, errors, file_count


def _zip_files_for_ccz(fpath, files, current_progress, file_progress, file_count, compression, task):
    file_cache = {}
    with open(fpath, 'wb') as tmp:
        with zipfile.ZipFile(tmp, "w", allowZip64=True) as z:
            for path, data in files:
                # don't compress multimedia files
                extension = os.path.splitext(path)[1]
                file_compression = zipfile.ZIP_STORED if extension in MULTIMEDIA_EXTENSIONS else compression
                z.writestr(path, data, file_compression)
                current_progress += file_progress / file_count
                DownloadBase.set_progress(task, current_progress, 100)
                if extension not in MULTIMEDIA_EXTENSIONS:
                    file_cache[path] = data
    return file_cache


def create_files_for_ccz(build, build_profile_id, include_multimedia_files=True, include_index_files=True,
                         download_id=None, compress_zip=False, filename="commcare.zip",
                         download_targeted_version=False, task=None):
    """
    :param task: celery task whose progress needs to be set when being run asynchronously by celery
    :return: path to the ccz file
    """
    compression = zipfile.ZIP_DEFLATED if compress_zip else zipfile.ZIP_STORED
    current_progress = 10  # early on indicate something is happening
    file_progress = 50.0  # arbitrarily say building files takes half the total time

    DownloadBase.set_progress(task, current_progress, 100)

    fpath = _get_file_path(build, include_multimedia_files, include_index_files, build_profile_id,
                           download_targeted_version)

    # Don't rebuild the file if it is already there
    if not (os.path.isfile(fpath) and settings.SHARED_DRIVE_CONF.transfer_enabled):
        with build.timing_context("_build_ccz_files"):
            files, errors, file_count = _build_ccz_files(
                build, build_profile_id, include_multimedia_files, include_index_files,
                download_id, compress_zip, filename, download_targeted_version
            )
        with build.timing_context("_zip_files_for_ccz"):
            file_cache = _zip_files_for_ccz(fpath, files, current_progress, file_progress,
                                            file_count, compression, task)

        if include_index_files and toggles.LOCALE_ID_INTEGRITY.enabled(build.domain):
            with build.timing_context("find_missing_locale_ids_in_ccz"):
                locale_errors = find_missing_locale_ids_in_ccz(file_cache)
            if locale_errors:
                errors.extend(locale_errors)
                notify_exception(
                    None,
                    message="CCZ missing locale ids from default/app_strings.txt",
                    details={'domain': build.domain, 'app_id': build.id, 'errors': locale_errors}
                )
        if include_index_files and include_multimedia_files:
            with build.timing_context("check_ccz_multimedia_integrity"):
                multimedia_errors = check_ccz_multimedia_integrity(build.domain, fpath)
            if multimedia_errors:
                multimedia_errors.insert(0, _(
                    "Please try syncing multimedia files in multimedia tab under app settings to resolve "
                    "issues with missing media files. Report an issue if this persists."
                ))
            errors.extend(multimedia_errors)
            if multimedia_errors:
                notify_exception(
                    None,
                    message="CCZ missing multimedia files",
                    details={'domain': build.domain, 'app_id': build.id, 'errors': multimedia_errors}
                )

        if errors:
            os.remove(fpath)
            raise Exception('\t' + '\t'.join(errors))
    else:
        DownloadBase.set_progress(task, current_progress + file_progress, 100)
    with build.timing_context("_expose_download_link"):
        _expose_download_link(fpath, filename, compress_zip, download_id)
    DownloadBase.set_progress(task, 100, 100)
    return fpath


def _expose_download_link(fpath, filename, compress_zip, download_id):
    common_kwargs = {
        'mimetype': 'application/zip' if compress_zip else 'application/x-zip-compressed',
        'content_disposition': 'attachment; filename="{fname}"'.format(fname=filename),
        'download_id': download_id,
        'expiry': (1 * 60 * 60),
    }
    if settings.SHARED_DRIVE_CONF.transfer_enabled:
        expose_file_download(fpath, use_transfer=True, **common_kwargs)
    else:
        expose_cached_download(FileWrapper(open(fpath, 'rb')),
                               file_extension=file_extention_from_filename(filename),
                               **common_kwargs)


def find_missing_locale_ids_in_ccz(file_cache):
    errors = [
        _("Could not find {file_path} in CCZ").format(file_path=file_path)
        for file_path in ('default/app_strings.txt', 'suite.xml') if file_path not in file_cache]
    if errors:
        return errors

    # Each line of an app_strings.txt file is of the format "name.of.key=value of key"
    # decode is necessary because Application._make_language_files calls .encode('utf-8')
    app_strings_ids = {
        line.decode("utf-8").split('=')[0]
        for line in file_cache['default/app_strings.txt'].splitlines()
    }

    from corehq.apps.app_manager.xform import parse_xml
    parsed = parse_xml(file_cache['suite.xml'])
    suite_ids = {locale.get("id") for locale in parsed.iter("locale")}

    return [
        _("Locale ID {id} present in suite.xml but not in default app strings.").format(id=id)
        for id in (suite_ids - app_strings_ids) if id
    ]


# Check that all media files present in media_suite.xml were added to the zip
def check_ccz_multimedia_integrity(domain, fpath):
    errors = []

    with open(fpath, 'rb') as tmp:
        with zipfile.ZipFile(tmp, "r") as z:
            media_suites = [f for f in z.namelist() if re.search(r'\bmedia_suite.xml\b', f)]
            if len(media_suites) != 1:
                message = _('Could not find media_suite.xml in CCZ')
                errors.append(message)
            else:
                with z.open(media_suites[0]) as media_suite:
                    from corehq.apps.app_manager.xform import parse_xml
                    parsed = parse_xml(media_suite.read())
                    resources = {node.text for node in
                                 parsed.findall("media/resource/location[@authority='local']")}
                    names = z.namelist()
                    missing = [r for r in resources if re.sub(r'^\.\/', '', r) not in names]
                    errors += [_('Media file missing from CCZ: {}').format(r) for r in missing]

    return errors
