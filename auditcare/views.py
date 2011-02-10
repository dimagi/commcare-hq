from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse

from models import *
from django.contrib.auth.decorators import login_required
from patient.models.couchmodels import CPatient
from couchforms.models import XFormInstance
import datetime


def auditAll(request, template="index.html"):
    auditEvents = couchmodels.AuditEvent.view("auditcare/audit_events_dates").all()

    realEvents = [{"user":a["key"][0], "type":a["key"][1], "path":a["key"][2], "date":
                    datetime.datetime(year=int(a["key"][3]),
                                      month=int(a["key"][4]),
                                      day=int(a["key"][5]),
                                      hour=a["key"][6],
                                      minute=a["key"][7],
                                      second=a["key"][8])} for a in auditEvents]
    return render_to_response(template, {"auditEvents": realEvents})
