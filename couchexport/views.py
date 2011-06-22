from couchexport.export import export, Format
from django.http import HttpResponse
from StringIO import StringIO
import json

def export_data(request, **kwargs):
    """
    Download all data for a couchdbkit model
    """
    export_tag = request.GET.get("export_tag", "")
    if not export_tag:
        raise Exception("You must specify a model to download!")
    try:
        # try to parse this like a compound json list 
        export_tag = json.loads(request.GET.get("export_tag", ""))
    except ValueError:
        pass # assume it was a string
    format = Format.from_format(request.GET.get("format", Format.XLS_2007))
    
    filename_base = request.GET.get("filename", export_tag)
    tmp = StringIO()
    if export(export_tag, tmp, format=format.slug):
        response = HttpResponse(mimetype=format.mimetype)
        response['Content-Disposition'] = 'attachment; filename=%s.%s' % \
                                        (filename_base, format.extension)
        response.write(tmp.getvalue())
        tmp.close()
        return response
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)
