from wsgiref.util import FileWrapper
from django.http.response import StreamingHttpResponse
from couchexport.export import Format
from django.http import HttpResponse
import json
from couchexport.shortcuts import export_data_shared
from couchexport.models import GroupExportConfiguration, SavedBasicExport, DefaultExportSchema
from django.shortcuts import render_to_response
from django.template.context import RequestContext
import unicodedata

def _export_tag_or_bust(request):
    export_tag = request.GET.get("export_tag", "")
    if not export_tag:
        raise Exception("You must specify a model to download!")
    try:
        # try to parse this like a compound json list
        export_tag = json.loads(request.GET.get("export_tag", ""))
    except ValueError:
        pass # assume it was a string
    return export_tag

def export_data_async(request, filter=None, **kwargs):
    format = request.GET.get("format", Format.XLS_2007)
    filename = request.GET.get("filename", None)
    previous_export_id = request.GET.get("previous_export", None)

    export_tag = _export_tag_or_bust(request)
    export_object = DefaultExportSchema(index=export_tag)

    return export_object.export_data_async(
        filter=filter,
        filename=filename,
        previous_export_id=previous_export_id,
        format=format
    )

def export_data(request, **kwargs):
    """
    Download all data for a couchdbkit model
    """
    export_tag = _export_tag_or_bust(request)
    resp = export_data_shared(export_tag,
                              format=request.GET.get("format", Format.XLS_2007),
                              filename=request.GET.get("filename", None),
                              previous_export_id=request.GET.get("previous_export", None),
                              separator=request.GET.get("separator", "|"))
    if resp:
        return resp
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)


def download_saved_export(request, export_id):
    export = SavedBasicExport.get(export_id)
    content_type = Format.from_format(export.configuration.format).mimetype
    payload = export.get_payload(stream=True)
    response = StreamingHttpResponse(FileWrapper(payload), content_type=content_type)
    if export.configuration.format != 'html':
        # ht: http://stackoverflow.com/questions/1207457/convert-unicode-to-string-in-python-containing-extra-symbols
        normalized_filename = unicodedata.normalize(
            'NFKD', unicode(export.configuration.filename),
        ).encode('ascii', 'ignore')
        response['Content-Disposition'] = 'attachment; filename="%s"' % normalized_filename
    return response
