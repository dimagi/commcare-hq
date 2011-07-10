from couchexport.export import Format
from django.http import HttpResponse
import json
from couchexport.shortcuts import export_data_shared

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
    
    resp = export_data_shared(export_tag, 
                              request.GET.get("format", Format.XLS_2007), 
                              request.GET.get("filename", None)) 
    if resp:
        return resp
    else:
        return HttpResponse("Sorry, there was no data found for the tag '%s'." % export_tag)
    
