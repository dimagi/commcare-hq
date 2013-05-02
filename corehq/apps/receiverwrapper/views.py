import receiver.views as rec_views
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

# we have to wrap the receiver views because of the extra domain argument
# in the url
def form_list(request, domain):
    # todo: deal with domain
    return rec_views.form_list(request)

@csrf_exempt    
@require_POST
def post(request, domain, app_id=None):
    return rec_views.post(request)

