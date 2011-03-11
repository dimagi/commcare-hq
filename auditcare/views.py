from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.contrib.auth import authenticate
from django.contrib.auth.views import login as django_login, logout as django_logout
from signals import *
from models import *
import datetime


def auditAll(request, template="auditcare/index.html"):
    auditEvents = couchmodels.AuditEvent.view("auditcare/by_user_date").all()
    context = RequestContext(request)

    realEvents = [{"user":a["key"][0], "path":a["value"], "date":
                    datetime.datetime(year=int(a["key"][1]),
                                      month=int(a["key"][2]),
                                      day=int(a["key"][3]),
                                      hour=a["key"][4],
                                      minute=a["key"][5],
                                      second=a["key"][6])} for a in auditEvents]
    context['auditEvents'] = realEvents
    return render_to_response(template, context)

def audit_login_view(request, template_name, *args, **kwargs):
    username=request.POST.get('username')
    u = authenticate(username=username,password=request.POST.get('password'))
    if u is None or not u.is_active:
        user_login_failed.send(sender=None,request=request,username=username) # This is new
    elif u.is_active:
        pass
    return django_login(request, *args, **kwargs)

def audit_logout_view(request, *args, **kwargs):

    return django_login(request, *args, **kwargs)
