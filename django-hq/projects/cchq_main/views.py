from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.template import RequestContext
from django.core.exceptions import *
from django.shortcuts import render_to_response, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.utils.translation import ugettext_lazy as _
from django.db.models.query_utils import Q

from datetime import timedelta

import uuid

from django.contrib.auth.models import User 


import logging

def homepage(request,template_name='cchq_main_homepage.html'):
    return_dict = {}    
    current_user = request.user
    #return_dict['user'] = current_user        
    return render_to_response(template_name,return_dict, context_instance=RequestContext(request))



