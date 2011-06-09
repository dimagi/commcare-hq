from django.http import HttpResponse
from django_digest.decorators import *
from casexml.apps.phone import xml
from dimagi.utils.timeout import TimeoutException
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.restore import generate_restore_payload



@httpdigest
def restore(request):
    user = request.user
    restore_id = request.GET.get('since')
    
    try:
        response = generate_restore_payload(user, restore_id)
        return HttpResponse(response, mimetype="text/xml")
    except TimeoutException:
        return HttpResponse(status=503)
    

def xml_for_case(request, case_id):
    """
    Test view to get the xml for a particular case
    """
    case = CommCareCase.get(case_id)
    return HttpResponse(xml.get_case_xml(case), mimetype="text/xml")
    