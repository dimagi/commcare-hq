#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from corehq.apps.users.models import CouchUser
from corehq.util.webutils import render_to_response
from . import util

def messaging(request, domain, template="sms/default.html"):
    context = {}
    if request.method == "POST":
        if 'recipients[]' not in request.POST or 'text' not in request.POST:
            context['errors'] = "Error: must select at least 1 number and write a message."
        else:
            phone_numbers = request.POST.getlist('recipients[]')
            util.send_sms_messages(phone_numbers,
                                   text=request.POST["text"])
            return HttpResponseRedirect( reverse("messaging", kwargs={ "domain": domain} ) )
    phone_users = CouchUser.view("users/phone_users_by_domain", key=domain)
    context['domain'] = domain
    context['phone_users'] = [phone_user['value'] for phone_user in phone_users]
    return render_to_response(request, template, context)
