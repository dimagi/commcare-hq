import logging
from django.http import HttpResponse
from casexml.apps.case.models import CommCareCase
from couchforms.views import post as couchforms_post
import receiver.views as rec_views
from django.views.decorators.http import require_POST
from django.contrib.sites.models import Site
from couchforms.models import XFormInstance
from corehq.apps.phone import xml
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

# we have to wrap the receiver views because of the extra domain argument
# in the url
def form_list(request, domain):
    # todo: deal with domain
    return rec_views.form_list(request)

@csrf_exempt    
@require_POST
def post(request, domain):
    return rec_views.post(request)
