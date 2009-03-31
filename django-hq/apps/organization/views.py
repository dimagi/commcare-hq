# Create your views here.
from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q
from django.core.urlresolvers import reverse

from datetime import timedelta
from django.db import transaction


from modelrelationship.models import *
from organization.models import *

from django.contrib.auth.models import User 
from django.contrib.contenttypes.models import ContentType

#from forms import *
import logging
import hashlib
import settings
import traceback
import sys
import os
import string

@login_required()
def manager(request, template_name="organization/manager.html"):
    context = {}
    if ExtUser.objects.all().filter(id=request.user.id).count() == 0:
        template_name="organization/no_permission.html"
        return render_to_response(template_name, context, context_instance=RequestContext(request))
    
    contenttype_id = None
    content_id = None
    
    for item in request.GET.items():
        if item[0] == 'content_type':
            contenttype_id=item[1]
        if item[0] == 'content_id':
            content_id=item[1]
    
    if contenttype_id != None and content_id != None:
        ctype = ContentType.objects.all().get(id=contenttype_id)
        context['selected_type'] = ctype
        content_instance = ctype.model_class().objects.all().get(id=content_id)
        context['selected_object'] =  content_instance
    else:
        context['selected_object'] = None
    
    extuser = ExtUser.objects.all().get(id=request.user.id)        
    context['extuser'] = extuser    
    return render_to_response(template_name, context, context_instance=RequestContext(request))
