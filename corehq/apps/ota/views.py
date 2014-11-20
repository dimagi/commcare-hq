from casexml.apps.case.xml import V2
from corehq.apps.domain.decorators import require_superuser
from corehq.apps.domain.models import Domain
from corehq.apps.ota.tasks import prime_restore
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.util.view_utils import json_error
from django_digest.decorators import *
from casexml.apps.phone.restore import RestoreConfig
from django.http import HttpResponse


@json_error
@httpdigest
def restore(request, domain):
    """
    We override restore because we have to supply our own 
    user model (and have the domain in the url)
    """
    user = request.user
    couch_user = CouchUser.from_django_user(user)
    return get_restore_response(domain, couch_user, **get_restore_params(request))


@require_superuser
def prime_ota_restore_cache(request, domain):
    params = get_restore_params(request)

    user_ids = CommCareUser.ids_by_domain(domain)
    cache_timeout = 24 * 60 * 60

    def make_args(user_id):
        return (
            user_id,
            params['since'],
            params['version'],
            params['state'],
            params['items'],
            cache_timeout
        )

    prime_restore.starmap(make_args(user_id) for user_id in user_ids).apply_async()

    return HttpResponse()


def get_restore_params(request):
    """
    Given a request, get the relevant restore parameters out with sensible defaults
    """
    # not a view just a view util
    return {
        'since': request.GET.get('since'),
        'version': request.GET.get('version', "1.0"),
        'state': request.GET.get('state'),
        'items': request.GET.get('items') == 'true'
    }


def get_restore_response(domain, couch_user, since=None, version='1.0',
                         state=None, items=False, force_cache=False, cache_timeout=None):
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
        items=items,
        stock_settings=stock_settings,
        domain=project,
        force_cache=force_cache,
        cache_timeout=cache_timeout
    )
    return restore_config.get_response()
