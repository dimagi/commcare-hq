import json
from django.http import HttpResponse


def set_file_download(response, filename):
    response["Content-Disposition"] = 'attachment; filename="%s"' % filename


def json_error(f):
    def inner(request, *args, **kwargs):
        try:
            response = f(request, *args, **kwargs)
        except Exception as e:
            data = {
                'error_message': unicode(e),
            }
            return HttpResponse(status=500, content=json.dumps(data), content_type='application/json')
        return response
    return inner
