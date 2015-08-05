from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, Http404
import couchforms
from couchforms.models import XFormInstance
from couchforms.util import SubmissionPost


@require_POST
@csrf_exempt
def post(request):
    """
    XForms can get posted here.  They will be forwarded to couch.
    
    Just like play, if you specify a callback you get called, 
    otherwise you get a generic response.  Callbacks follow
    a different signature as play, only passing in the document
    (since we don't know what xform was being posted to)
    """
    instance, attachments = couchforms.get_instance_and_attachment(request)
    return SubmissionPost(
        instance=instance,
        attachments=attachments,
        path=couchforms.get_path(request),
    ).get_response()


def download_form(request, instance_id):
    instance = XFormInstance.get(instance_id) 
    response = HttpResponse(content_type='application/xml')
    response.write(instance.get_xml())
    # if we want it to download like a file put somethingl like this
    # HttpResponse(content_type='application/vnd.ms-excel')
    # response['Content-Disposition'] = 'attachment; filename=%s.xml' % instance_id
    return response


def download_attachment(request, instance_id, attachment):
    instance = XFormInstance.get(instance_id)
    try:
        attach = instance._attachments[attachment]
    except KeyError:
        raise Http404()
    response = HttpResponse(content_type=attach["content_type"])
    response.write(instance.fetch_attachment(attachment))
    return response
