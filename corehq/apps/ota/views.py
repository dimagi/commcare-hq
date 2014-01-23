from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser
from django_digest.decorators import *
from casexml.apps.phone.restore import RestoreConfig
from django.http import HttpResponse

@httpdigest
def restore(request, domain):
    """
    We override restore because we have to supply our own 
    user model (and have the domain in the url)
    """
    user = request.user
    couch_user = CouchUser.from_django_user(user)
    return get_restore_response(domain, couch_user, **get_restore_params(request))

def get_restore_params(request):
    """
    Given a request, get the relevant restore parameters out with sensible defaults
    """
    # not a view just a view util
    return {
        'since': request.GET.get('since'),
        'version': request.GET.get('version', "1.0"),
        'state': request.GET.get('state'),
    }

def get_restore_response(domain, couch_user, since=None, version='1.0', state=None):
    # not a view just a view util
    if not couch_user.is_commcare_user():
        return HttpResponse("No linked chw found for %s" % couch_user.username,
                            status=401)  # Authentication Failure
    elif domain != couch_user.domain:
        return HttpResponse("%s was not in the domain %s" % (couch_user.username, domain),
                            status=401)

    project = Domain.get_by_name(domain)
    commtrack_settings = project.commtrack_settings
    stock_settings = commtrack_settings.get_ota_restore_settings() if commtrack_settings else None
    restore_config = RestoreConfig(
        couch_user.to_casexml_user(), since, version, state,
        caching_enabled=project.ota_restore_caching,
        stock_settings=stock_settings,
    )
    return restore_config.get_response()
