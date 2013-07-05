from corehq.apps.domain.decorators import login_or_digest_ex
import receiver.views as rec_views
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
@require_POST
def post(request, domain, app_id=None):
    return rec_views.post(request)

@login_or_digest_ex(allow_cc_users=True)
def secure_post(request, domain, app_id=None):
    # this doesn't check yet if the submitting user
    # is the user in the meta username/userID
    return post(request, domain, app_id=app_id)
