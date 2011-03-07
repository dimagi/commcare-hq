from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.contrib.auth import authenticate
from django.contrib.auth.views import login as django_login
from signals import *
from models import *
import datetime


def auditAll(request, template="auditcare/index.html"):
    auditEvents = couchmodels.AuditEvent.view("auditcare/by_date").all()
    context = RequestContext(request)

    realEvents = [{"user":a["key"][0], "type":a["key"][1], "path":a["key"][2], "date":
                    datetime.datetime(year=int(a["key"][3]),
                                      month=int(a["key"][4]),
                                      day=int(a["key"][5]),
                                      hour=a["key"][6],
                                      minute=a["key"][7],
                                      second=a["key"][8])} for a in auditEvents]
    context['auditEvents'] = realEvents
    return render_to_response(template, context)

def audit_login(request, template_name, *args, **kwargs):
    username=request.POST.get('username')
    u = authenticate(username=username,password=request.POST.get('password'))
    if u is None or not u.is_active:
        user_login_failed.send(sender=None,request=request,username=username) # This is new
    return django_login(request, *args, **kwargs)

#django.contrib.auth.views.login = audit_login
