from django.http import HttpResponseBadRequest
from corehq.apps.domain.decorators import login_or_digest_ex
from corehq.apps.receiverwrapper.auth import AuthContext
import receiver
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


def _process_form(request, domain, app_id, user_id, authenticated):
    instance, attachments = receiver.get_instance_and_attachment(request)
    return receiver.SubmissionPost(
        instance=instance,
        attachments=attachments,
        domain=domain,
        app_id=app_id,
        auth_context=AuthContext(
            domain=domain,
            user_id=user_id,
            authenticated=authenticated,
        ),
        location=receiver.get_location(request),
        received_on=receiver.get_received_on(request),
        date_header=receiver.get_date_header(request),
        path=receiver.get_path(request),
        submit_ip=receiver.get_submit_ip(request),
        last_sync_token=receiver.get_last_sync_token(request),
        openrosa_headers=receiver.get_openrosa_headers(request),
    ).get_response()


@csrf_exempt
@require_POST
def post(request, domain, app_id=None):
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=None,
        authenticated=False,
    )


@login_or_digest_ex(allow_cc_users=True)
def _secure_post_digest(request, domain, app_id=None):
    """only ever called from secure post"""
    return _process_form(
        request=request,
        domain=domain,
        app_id=app_id,
        user_id=request.couch_user.get_id,
        authenticated=True,
    )


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
