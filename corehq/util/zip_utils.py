import os
import tempfile
import itertools
import uuid
from wsgiref.util import FileWrapper
import zipfile

from soil import DownloadBase
from django.conf import settings

from django.http import StreamingHttpResponse
from django.views.generic import View
from django_transfer import TransferHttpResponse, is_enabled as transfer_enabled
from corehq.util.view_utils import set_file_download
from soil.util import expose_cached_download, expose_file_download

CHUNK_SIZE = 8192
MULTIMEDIA_EXTENSIONS = ('.mp3', '.wav', '.jpg', '.png', '.gif', '.3gp', '.mp4', '.zip', )


def make_zip_file(files, compress=True, path=None):
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    fpath = path
    if not fpath:
        _, fpath = tempfile.mkstemp()

    with open(fpath, 'wb') as tmp:
        with zipfile.ZipFile(tmp, "w", compression) as z:
            for path, data in files:
                z.writestr(path, data)
    return fpath


class DownloadZip(View):
    compress_zip = None
    zip_name = None
    download_async = False

    @property
    def zip_mimetype(self):
        if self.compress_zip:
            return 'application/zip'
        else:
            return 'application/x-zip-compressed'

    def log_errors(self, errors):
        raise NotImplementedError()

    def iter_files(self):
        raise NotImplementedError()

    def check_before_zipping(self):
        raise NotImplementedError()

    def get(self, request, *args, **kwargs):
        error_response = self.check_before_zipping()
        if error_response:
            return error_response

        path = None
        if transfer_enabled() and os.path.isdir(settings.TRANSFER_FILE_DIR):
            path = os.path.join(settings.TRANSFER_FILE_DIR, uuid.uuid4().hex)

        files, errors = self.iter_files()
        fpath = make_zip_file(files, compress=self.compress_zip, path=path)
        if errors:
            self.log_errors(errors)

        if transfer_enabled():
            return TransferHttpResponse(fpath, mimetype=self.zip_mimetype)
        else:
            response = StreamingHttpResponse(FileWrapper(open(fpath), CHUNK_SIZE), mimetype=self.zip_mimetype)
            response['Content-Length'] = os.path.getsize(fpath)
            set_file_download(response, self.zip_name)
            return response


def iter_files_async(include_multimedia_files, include_index_files, app):
    file_iterator = lambda: iter([])
    errors = []
    if include_multimedia_files:
        from corehq.apps.hqmedia.views import iter_media_files
        app.remove_unused_mappings()
        file_iterator, errors = iter_media_files(app.get_media_objects())
    if include_index_files:
        from corehq.apps.app_manager.views import iter_index_files
        if app.is_remote_app():
            file_iterator, errors = iter_index_files(app)
        else:
            index_files, index_file_errors = iter_index_files(app)
            if index_file_errors:
                errors.append(index_file_errors)
            file_iterator = itertools.chain(file_iterator, index_files)

    return file_iterator, errors


def make_zip_tempfile_async(include_multimedia_files,
                            include_index_files, app, download_id, compress_zip=False, filename="commcare.zip"):
    compression = zipfile.ZIP_DEFLATED if compress_zip else zipfile.ZIP_STORED

    use_transfer = False
    if transfer_enabled() and os.path.isdir(settings.TRANSFER_FILE_DIR):
        fpath = os.path.join(settings.TRANSFER_FILE_DIR, uuid.uuid4().hex)
        use_transfer = True
    else:
        _, fpath = tempfile.mkstemp()

    files, errors = iter_files_async(include_multimedia_files, include_index_files, app)
    with open(fpath, 'wb') as tmp:
        with zipfile.ZipFile(tmp, "w") as z:
            for path, data in files:
                # don't compress multimedia files
                extension = os.path.splitext(path)[1]
                file_compression = zipfile.ZIP_STORED if extension in MULTIMEDIA_EXTENSIONS else compression
                z.writestr(path, data, file_compression)

    return expose_file_download(fpath,
                                mimetype='application/zip' if compress_zip else 'application/x-zip-compressed',
                                download_id=download_id,
                                content_disposition='attachment; filename="{fname}"'.format(fname=filename),
                                use_transfer=use_transfer), errors


class DownloadZipAsync(DownloadZip):
    include_multimedia_files = False
    include_index_files = False

    def get(self, request, *args, **kwargs):
        from corehq.util.tasks import make_zip_tempfile_task
        error_response = self.check_before_zipping()
        if error_response:
            return error_response

        download = DownloadBase()
        download.set_task(make_zip_tempfile_task.delay(
            include_multimedia_files=self.include_multimedia_files,
            include_index_files=self.include_index_files,
            app=self.app,
            compress_zip=self.compress_zip,
            download_id=download.download_id,
            filename=self.zip_name)
        )
        return download.get_start_response()
