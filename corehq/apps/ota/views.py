from corehq.apps.users.models import CouchUser
from django_digest.decorators import *
from casexml.apps.phone.restore import generate_restore_response



@httpdigest
def restore(request, domain):
    """
    We override restore because we have to supply our own 
    user model (and have the domain in the url)
    """
    
    user = request.user
    restore_id = request.GET.get('since')
    api_version = request.GET.get('version', "1.0")
    state_hash = request.GET.get('state')
    username = user.username
    couch_user = CouchUser.from_django_user(user)
    
    if not couch_user.is_commcare_user():
        response = HttpResponse("No linked chw found for %s" % username)
        response.status_code = 401 # Authentication Failure
        return response
    
    return generate_restore_response(couch_user.to_casexml_user(), restore_id, 
                                         api_version, state_hash)
    