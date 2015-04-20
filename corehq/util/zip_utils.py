import os
import tempfile
from wsgiref.util import FileWrapper
import zipfile
from django.http import StreamingHttpResponse
from django.views.generic import View
from corehq.util.view_utils import set_file_download

CHUNK_SIZE = 8192


def make_zip_tempfile(files, compress=True):
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    fd, fpath = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as tmp:
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

        files, errors = self.iter_files()
        fpath = make_zip_tempfile(files, compress=self.compress_zip)
        if errors:
            self.log_errors(errors)

        response = StreamingHttpResponse(FileWrapper(open(fpath), CHUNK_SIZE), mimetype=self.zip_mimetype)
        response['Content-Length'] = os.path.getsize(fpath)
        set_file_download(response, self.zip_name)
        return response
