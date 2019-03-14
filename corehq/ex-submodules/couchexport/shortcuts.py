from __future__ import absolute_import
from __future__ import unicode_literals
import io
from wsgiref.util import FileWrapper

from couchexport.files import TempBase
from django.http import HttpResponse, StreamingHttpResponse


def export_response(file, format, filename, checkpoint=None):
    """
    Get an http response for an export
    file can be either a io.BytesIO or io.StringIO
    or an open file object (which this function is responsible for closing)

    """
    from couchexport.export import Format
    if not filename:
        filename = "NAMELESS EXPORT"

    format = Format.from_format(format)
    if isinstance(file, TempBase):
        file = file.file

    if isinstance(file, (io.BytesIO, io.StringIO)):
        response = HttpResponse(file.getvalue(), content_type=format.mimetype)
        # I don't know why we need to close the file. Keeping around.
        file.close()
    else:
        response = StreamingHttpResponse(FileWrapper(file), content_type=format.mimetype)

    if format.download:
        from corehq.util.files import safe_filename_header
        response['Content-Disposition'] = safe_filename_header(filename, format.extension)

    if checkpoint:
        response['X-CommCareHQ-Export-Token'] = checkpoint.get_id

    return response
