from couchexport.export import Format
from django.http import HttpResponse
import json
from couchexport.shortcuts import export_data_shared
from couchexport.models import GroupExportConfiguration, SavedBasicExport, FakeSavedExportSchema
from django.shortcuts import render_to_response
from django.template.context import RequestContext

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
    export_object = FakeSavedExportSchema(index=export_tag)

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
    
def view_export_group(request, group_id):
    group = GroupExportConfiguration.get(group_id)
    return render_to_response('couchexport/export_group.html',
                              {"group" : group},
                               context_instance=RequestContext(request))
                           
def download_saved_export(request, export_id):
    export = SavedBasicExport.get(export_id)
    attach = export._attachments[export.configuration.filename]
    response = HttpResponse(mimetype=attach["content_type"])
    response.write(export.fetch_attachment(export.configuration.filename))
    response['Content-Disposition'] = 'attachment; filename=%s' % export.configuration.filename
    return response