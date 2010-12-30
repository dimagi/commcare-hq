#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import logging
from datetime import datetime
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from corehq.apps.users.models import CouchUser
from corehq.apps.sms.models import MessageLog, INCOMING
from corehq.apps.groups.models import Group
from corehq.util.webutils import render_to_response
from . import util

def messaging(request, domain, template="sms/default.html"):
    context = {}
    if request.method == "POST":
        if ('recipients[]' not in request.POST and 'grouprecipients[]' not in request.POST) \
          or 'text' not in request.POST:
            context['errors'] = "Error: must select at least 1 recipient and write a message."
        else:
            num_errors = 0
            text = request.POST["text"]
            if 'recipients[]' in request.POST:
                phone_numbers = request.POST.getlist('recipients[]')
                for phone_number in phone_numbers:
                    id, phone_number = phone_number.split('_')
                    success = util.send_sms(domain, id, phone_number, text)
                    if not success:
                        num_errors = num_errors + 1
            else:            
                groups = request.POST.getlist('grouprecipients[]')
                for group_id in groups:
                    group = Group.get(group_id)
                    users = CouchUser.view("users/by_group", key=group.name).all()
                    user_ids = [m['value'] for m in CouchUser.view("users/by_group", key=group.name).all()]
                    users = [m for m in CouchUser.view("users/all_users", keys=user_ids).all()]
                    for user in users: 
                        success = util.send_sms(domain, 
                                                user.get_id, 
                                                user.default_phone_number(), 
                                                text)
                        if not success:
                            num_errors = num_errors + 1
            if num_errors > 0:
                context['errors'] = "Could not send %s messages" % num_errors
            else:
                return HttpResponseRedirect( reverse("messaging", kwargs={ "domain": domain} ) )
    phone_users_raw = CouchUser.view("users/phone_users_by_domain", key=domain)
    context['domain'] = domain
    phone_users = []
    for phone_user in phone_users_raw:
        phone_users.append( PhoneUser(id = phone_user['id'],
                                      name = phone_user['value'][0],
                                      phone_number = phone_user['value'][1]))
    groups = Group.view("groups/by_domain", key=domain)
    context['phone_users'] = phone_users
    context['groups'] = groups
    context['messagelog'] = MessageLog.objects.filter(domain=domain)
    return render_to_response(request, template, context)

class PhoneUser(object):
    """ this class is purely for better readability/debuggability """
    def __init__(self, id="", name="", phone_number=""):
        self.id = id
        self.name = name
        self.phone_number = phone_number

def post(request, domain):
    """
    We assume sms sent to HQ will come in the form
    http://hqurl.com?username=%(username)s&password=%(password)s&id=%(phone_number)s&text=%(message)s
    """
    text = request.REQUEST.get('text', '')
    to = request.REQUEST.get('id', '')
    username = request.REQUEST.get('username', '')
    # ah, plaintext passwords....  
    # this seems to be the most common API that a lot of SMS gateways expose
    password = request.REQUEST.get('password', '')
    if not text or not to or not username or not password:
        error_msg = 'ERROR missing parameters. Received: %(1)s, %(2)s, %(3)s, %(4)s' % \
                     ( text, to, username, password )
        logging.error(error_msg)
        return HttpResponseBadRequest(error_msg)
    user = authenticate(username=username, password=password)
    if user is None or not user.is_active:
        return HttpResponseBadRequest("Authentication fail")
    msg = MessageLog(domain=domain,
                     # how to map phone numbers to recipients, when phone numbers are shared?
                     #couch_recipient=id, 
                     phone_number=to,
                     direction=INCOMING,
                     date = datetime.now(),
                     text = text)
    msg.save()
    return HttpResponse('OK')     
