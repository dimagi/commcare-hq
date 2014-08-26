import json
import traceback
from django.http import HttpResponse


def set_file_download(response, filename):
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename


def produce_structured_response(f):
    def inner(request, *args, **kwargs):
        try:
            response = f(request, *args, **kwargs)
        except Exception as e:
            import sys
            the_trace = '\n'.join(traceback.format_exception(*(sys.exc_info())))
            data = {
                'error_message': e.message,
                'traceback': the_trace
            }
            return HttpResponse(status=500, content=json.dumps(data), content_type='application/json')
        return response
    return inner
