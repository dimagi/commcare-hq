from __future__ import absolute_import
from __future__ import unicode_literals

import itertools
from wsgiref.util import FileWrapper

from django.http import StreamingHttpResponse, HttpResponse
from werkzeug.http import parse_range_header

from corehq.util.files import safe_filename_header


class RangedFileWrapper(object):
    """
    Wraps a file like object with an iterator that runs over part (or all) of
    the file defined by start and stop. Blocks of block_size will be returned
    from the starting position, up to, but not including the stop point.

    Based off: https://github.com/satchamo/django/commit/2ce75c5c4bee2a858c0214d136bfcd351fcde11d
    """
    block_size = 8192

    def __init__(self, filelike, start=0, stop=float("inf"), block_size=None):
        self.filelike = filelike
        self.block_size = block_size or RangedFileWrapper.block_size
        self.start = start
        self.stop = stop
        if hasattr(filelike, 'close'):
            self.close = filelike.close

    def __iter__(self):

        def _partial_read(current_position, stop):
            """Read blocks of data from current position until ``stop`` position or end of file."""
            while current_position < stop:
                data = self.filelike.read(min(self.block_size, stop - current_position))
                current_position += len(data)
                if not data:
                    break

                yield data

        if hasattr(self.filelike, 'seek'):
            self.filelike.seek(self.start)
        else:
            list(itertools.dropwhile(lambda x: True, _partial_read(0, self.start)))

        for data in _partial_read(self.start, self.stop):
            yield data


def get_download_response(payload, content_length, content_format, filename, request=None):
    """
    :param payload: File like object.
    :param content_length: Size of payload in bytes
    :param content_format: ``couchexport.models.Format`` instance
    :param filename: Name of the download
    :param request: The request. Used to determine if a range response should be given.
    :return: HTTP response
    """
    ranges = None
    if request and "HTTP_RANGE" in request.META:
        try:
            ranges = parse_range_header(request.META['HTTP_RANGE'], content_length)
        except ValueError:
            pass

    if ranges and len(ranges.ranges) != 1:
        ranges = None

    response = StreamingHttpResponse(content_type=content_format.mimetype)
    if content_format.download:
        response['Content-Disposition'] = safe_filename_header(filename)

    response["Content-Length"] = content_length
    response["Accept-Ranges"] = "bytes"

    if ranges:
        start, stop = ranges.ranges[0]
        if stop is not None and stop > content_length:
            # requested range not satisfiable
            return HttpResponse(status=416)

        response.streaming_content = RangedFileWrapper(payload, start=start, stop=stop or float("inf"))
        end = stop or content_length
        response["Content-Range"] = "bytes %d-%d/%d" % (start, end - 1, content_length)
        response["Content-Length"] = end - start
        response.status_code = 206
    else:
        response.streaming_content = FileWrapper(payload)

    return response
