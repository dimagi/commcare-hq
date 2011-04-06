from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.contrib.auth import authenticate
from signals import *
from models import *
import datetime


def auditAll(request, template="auditcare/index.html"):
    auditEvents = couchmodels.AccessAudit.view("auditcare/by_date_access_events", descending=True, include_docs=True).all()
    context = RequestContext(request)

    realEvents = [{'user': a.user, 'date': a.event_date, 'class': a.event_class, 'access_type': a.access_type } for a in auditEvents]

#    realEvents = [{"user":a["key"][0], "path":a["value"], "date":
#                    datetime.datetime(year=int(a["key"][1]),
#                                      month=int(a["key"][2]),
#                                      day=int(a["key"][3]),
#                                      hour=a["key"][4],
#                                      minute=a["key"][5],
#                                      second=a["key"][6])
#                  }
#                  for a in auditEvents]
    context['auditEvents'] = realEvents
    return render_to_response(template, context)


