from django.http import HttpResponseBadRequest
from corehq.apps.domain.decorators import login_or_digest_ex
from corehq.apps.receiverwrapper.auth import AuthContext
import receiver.views
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_POST
def post(request, domain, app_id=None):
    return receiver.views.SubmissionPost(request, auth_context=AuthContext(
        domain=domain,
        user_id=None,
        authenticated=False,
    )).get_response()


@login_or_digest_ex(allow_cc_users=True)
def _secure_post_digest(request, domain, app_id=None):
    """only ever called from secure post"""
    return receiver.views.SubmissionPost(request, auth_context=AuthContext(
        domain=domain,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )).get_response()


@csrf_exempt
@require_POST
def secure_post(request, domain, app_id=None):
    authtype = request.GET.get('authtype', 'digest')

    authtype_map = {
        'digest': _secure_post_digest,
        'noauth': post,
    }

    try:
        decorated_view = authtype_map[authtype]
    except KeyError:
        return HttpResponseBadRequest(
            'authtype must be one of: {0}'.format(','.join(authtype_map.keys()))
        )

    return decorated_view(request, domain, app_id=app_id)
