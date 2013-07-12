from django.http import HttpResponseBadRequest
from corehq.apps.domain.decorators import login_or_digest_ex
import receiver.views as rec_views
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_POST
def post(request, domain, app_id=None):
    return rec_views.post(request)


@csrf_exempt
@require_POST
def secure_post(request, domain, app_id=None):
    authtype = request.GET.get('authtype', 'digest')

    authtype_map = {
        'digest': login_or_digest_ex(allow_cc_users=True),
        'noauth': lambda f: f,
    }

    try:
        decorator = authtype_map[authtype]
    except KeyError:
        return HttpResponseBadRequest(
            'authtype must be one of: {0}'.format(','.join(authtype_map.keys()))
        )

    return decorator(post)(request, domain, app_id=app_id)
