import datetime
import os
import logging

from hq.models import ExtUser
from hq.models import Domain
from requestlogger.decorators import log_request                   

from rapidsms.webui.utils import render_to_response

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.http import *
from django.http import HttpResponse
from django.http import HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse

import mimetypes
import urllib

@log_request()
def demo(request):
    return HttpResponse("Thanks!")
    
