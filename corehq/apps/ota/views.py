from django.http import HttpResponse
from django_digest.decorators import *
from corehq.apps.users.util import couch_user_from_django_user
from casexml.apps.phone.restore import generate_restore_payload



@httpdigest
def restore(request, domain):
    """
    We override restore because we have to supply our own 
    user model (and have the domain in the url)
    """
    
    user = request.user
    restore_id = request.GET.get('since')
    username = user.username
    couch_user = couch_user_from_django_user(user)
    
    if not couch_user.is_commcare_user():
        response = HttpResponse("No linked chw found for %s" % username)
        response.status_code = 401 # Authentication Failure
        return response
    
    response = generate_restore_payload(couch_user.to_casexml_user(), restore_id)
    return HttpResponse(response, mimetype="text/xml")