from django.http import HttpResponse, Http404
from couchforms.models import XFormInstance


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
