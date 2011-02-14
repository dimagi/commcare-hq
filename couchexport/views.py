from couchexport.export import export, Format
from django.http import HttpResponse
from StringIO import StringIO
import json

def export_data(request, **kwargs):
    """
    Download all data for a couchdbkit model
    """
    export_tag = json.loads(request.GET.get("export_tag", ""))
    format = request.GET.get("format", Format.XLS_2007)
    if not export_tag:
        raise Exception("You must specify a model to download!")
    tmp = StringIO()
    if export(export_tag, tmp, format=format):
        response = HttpResponse(mimetype='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename=%s.%s' % (export_tag, format)
        response.write(tmp.getvalue())
        tmp.close()
        return response
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)
