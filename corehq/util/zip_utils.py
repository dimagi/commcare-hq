import os
import tempfile
import uuid
from wsgiref.util import FileWrapper
import zipfile
from django.conf import settings
from django.http import StreamingHttpResponse
from django.views.generic import View
from django_transfer import TransferHttpResponse
from corehq.util.view_utils import set_file_download

CHUNK_SIZE = 8192


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
        transfer_enabled = settings.SHARED_DRIVE_CONF.transfer_enabled
        if transfer_enabled:
            path = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, uuid.uuid4().hex)

        files, errors = self.iter_files()
        fpath = make_zip_file(files, compress=self.compress_zip, path=path)
        if errors:
            self.log_errors(errors)

        if transfer_enabled:
            return TransferHttpResponse(fpath, content_type=self.zip_mimetype)
        else:
            response = StreamingHttpResponse(FileWrapper(open(fpath), CHUNK_SIZE),
                    content_type=self.zip_mimetype)
            response['Content-Length'] = os.path.getsize(fpath)
            set_file_download(response, self.zip_name)
            return response
