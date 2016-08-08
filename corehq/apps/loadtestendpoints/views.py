from django.http import HttpResponse
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance
from django_digest.decorators import httpdigest


@httpdigest
def noop(request):
    return HttpResponse('Thanks for submitting', status=201)


@httpdigest
def saving(request):
    xform = XFormInstance()
    xform.deferred_put_attachment('-', 'form.xml')
    xform.save()
    case = CommCareCase()
    case.save()
    xform.initial_processing_complete = True
    xform.save()
    case.delete()
    xform.delete()
    return HttpResponse('Thanks for submitting', status=201)
