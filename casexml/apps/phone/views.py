from django.http import HttpResponse
from django_digest.decorators import *
from casexml.apps.phone import xml
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.restore import generate_restore_response
from casexml.apps.phone.models import User
from casexml.apps.case import const



@httpdigest
def restore(request):
    user = User.from_django_user(request.user)
    restore_id = request.GET.get('since')
    return generate_restore_response(user, restore_id)
    

def xml_for_case(request, case_id, version="1.0"):
    """
    Test view to get the xml for a particular case
    """
    case = CommCareCase.get(case_id)
    return HttpResponse(xml.get_case_xml(case, [const.CASE_ACTION_CREATE,
                                                const.CASE_ACTION_UPDATE],
                                         version), mimetype="text/xml")
    