from couchexport.export import Format
from django.http import HttpResponse, HttpResponseRedirect
import json
from couchexport.shortcuts import export_data_shared
import uuid
from couchexport.tasks import export_async
from django.core.urlresolvers import reverse

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

def export_data_async(request, **kwargs):
    export_tag = _export_tag_or_bust(request)
    download_id = uuid.uuid4().hex
    export_async.delay(download_id, export_tag, 
                       request.GET.get("format", Format.XLS_2007), 
                       request.GET.get("filename", None), 
                       request.GET.get("previous_export", None))
    return HttpResponseRedirect(reverse('retrieve_download', kwargs={'download_id': download_id}))
    
def export_data(request, **kwargs):
    """
    Download all data for a couchdbkit model
    """
    export_tag = _export_tag_or_bust(request)
    resp = export_data_shared(export_tag, 
                              request.GET.get("format", Format.XLS_2007), 
                              request.GET.get("filename", None), 
                              request.GET.get("previous_export", None)) 
    if resp:
        return resp
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)
    
