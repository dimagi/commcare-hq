from django.views.decorators.http import require_POST
from corehq.apps.analytics.tasks import track_clicked_deploy_on_hubspot
from django.http import HttpResponse

@require_POST
def hubspot_click_deploy(request):
    meta = {
            'HTTP_X_FORWARDED_FOR': request.META.get('HTTP_X_FORWARDED_FOR'),
            'REMOTE_ADDR': request.META.get('REMOTE_ADDR'),
    }
    track_clicked_deploy_on_hubspot.delay(request.couch_user, request.COOKIES, meta)
    return HttpResponse()