#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import json

import logging
from datetime import datetime
import re
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from corehq.apps.sms.api import send_sms, incoming, send_sms_with_backend
from corehq.apps.users.models import CouchUser
from corehq.apps.users import models as user_models
from corehq.apps.sms.models import SMSLog, INCOMING
from corehq.apps.groups.models import Group
from dimagi.utils.web import render_to_response
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest
from dimagi.utils.couch.database import get_db
from django.contrib import messages
from corehq.apps.reports import util as report_utils
from django.views.decorators.csrf import csrf_exempt

@login_and_domain_required
def messaging(request, domain, template="sms/default.html"):
    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['messagelog'] = SMSLog.by_domain_dsc(domain)
    context['now'] = datetime.utcnow()
    tz = report_utils.get_timezone(request.couch_user.user_id, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    context['layout_flush_content'] = True
    return render_to_response(request, template, context)

@login_and_domain_required
def compose_message(request, domain, template="sms/compose.html"):
    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['now'] = datetime.utcnow()
    tz = report_utils.get_timezone(request.couch_user.user_id, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    return render_to_response(request, template, context)

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
    msg = SMSLog(domain=domain,
                 # TODO: how to map phone numbers to recipients, when phone numbers are shared?
                 #couch_recipient=id, 
                 phone_number=to,
                 direction=INCOMING,
                 date = datetime.now(),
                 text = text)
    msg.save()
    return HttpResponse('OK')     


def get_sms_autocomplete_context(request, domain):
    """A helper view for sms autocomplete"""
    phone_users = CouchUser.view("users/phone_users_by_domain",
        startkey=[domain], endkey=[domain, {}], include_docs=True
    )
    groups = Group.view("groups/by_domain", key=domain, include_docs=True)

    contacts = []
    contacts.extend(['%s [group]' % group.name for group in groups])
    user_id = None
    for user in phone_users:
        if user._id == user_id:
            continue
        contacts.append(user.username)
        user_id = user._id
    return {"sms_contacts": contacts}

@login_and_domain_required
def send_to_recipients(request, domain):
    recipients = request.POST.get('recipients')
    message = request.POST.get('message')
    if not recipients:
        messages.error(request, "You didn't specify any recipients")
    elif not message:
        messages.error(request, "You can't send an empty message")
    else:
        recipients = [x.strip() for x in recipients.split(',') if x.strip()]
        phone_numbers = []
        # formats: GroupName (group), "Username", +15555555555
        group_names = []
        usernames = []
        phone_numbers = []

        unknown_usernames = []
        GROUP = "[group]"

        for recipient in recipients:
            if recipient.endswith(GROUP):
                name = recipient[:-len(GROUP)].strip()
                group_names.append(name)
            elif re.match(r'^\+\d+', recipient): # here we expect it to have a plus sign
                def wrap_user_by_type(u):
                    return getattr(user_models, u['doc']['doc_type']).wrap(u['doc'])

                phone_users = CouchUser.view("users/by_default_phone", # search both with and w/o the plus
                    keys=[recipient, recipient[1:]], include_docs=True,
                    wrapper=wrap_user_by_type).all()

                phone_users = filter(lambda u: u.is_member_of(domain), phone_users)
                if len(phone_users) > 0:
                    phone_numbers.append((phone_users[0], recipient))
                else:
                    phone_numbers.append((None, recipient))
            elif re.match(r'[\w\.]+', recipient):
                usernames.append(recipient)
            else:
                unknown_usernames.append(recipient)


        login_ids = dict([(r['key'], r['id']) for r in get_db().view("users/by_username", keys=usernames).all()])
        for username in usernames:
            if username not in login_ids:
                unknown_usernames.append(username)
        login_ids = login_ids.values()

        users = []
        empty_groups = []
        if len(group_names) > 0:
            users.extend(CouchUser.view('users/by_group', keys=[[domain, gn] for gn in group_names],
                                        include_docs=True).all())
            if len(users) == 0:
                empty_groups = group_names

        users.extend(CouchUser.view('_all_docs', keys=login_ids, include_docs=True).all())
        users = [user for user in users if user.is_active and not user.is_deleted()]

        phone_numbers.extend([(user, user.phone_number) for user in users])

        failed_numbers = []
        no_numbers = []
        sent = []
        for user, number in phone_numbers:
            if not number:
                no_numbers.append(user.raw_username)
            elif send_sms(domain, user.user_id if user else "", number, message):
                sent.append("%s" % (user.raw_username if user else number))
            else:
                failed_numbers.append("%s (%s)" % (
                    number,
                    user.raw_username if user else "<no username>"
                ))

        if empty_groups or failed_numbers or unknown_usernames or no_numbers:
            if empty_groups:
                messages.error(request, "The following groups don't exist: %s"  % (', '.join(empty_groups)))
            if no_numbers:
                messages.error(request, "The following users don't have phone numbers: %s"  % (', '.join(no_numbers)))
            if failed_numbers:
                messages.error(request, "Couldn't send to the following number(s): %s" % (', '.join(failed_numbers)))
            if unknown_usernames:
                messages.error(request, "Couldn't find the following user(s): %s" % (', '.join(unknown_usernames)))
            if sent:
                messages.success(request, "Successfully sent: %s" % (', '.join(sent)))
            else:
                messages.info(request, "No messages were sent.")
        else:
            messages.success(request, "Message sent")

    return HttpResponseRedirect(
        request.META.get('HTTP_REFERER') or
        reverse(compose_message, args=[domain])
    )

@login_and_domain_required
def message_test(request, domain, phone_number):
    if request.method == "POST":
        message = request.POST.get("message", "")
        incoming(phone_number, message, "TEST")
    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['messagelog'] = SMSLog.by_domain_dsc(domain)
    context['now'] = datetime.utcnow()
    tz = report_utils.get_timezone(request.couch_user.user_id, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    context['layout_flush_content'] = True
    context['phone_number'] = phone_number
    return render_to_response(request, "sms/message_tester.html", context)

@csrf_exempt
@login_or_digest
def api_send_sms(request, domain):
    if request.method == "POST":
        phone_number = request.POST.get("phone_number", None)
        text = request.POST.get("text", None)
        backend_id = request.POST.get("backend_id", None)
        if (phone_number is None) or (text is None) or (backend_id is None):
            return HttpResponseBadRequest("Not enough arguments.")
        if send_sms_with_backend(domain, phone_number, text, backend_id):
            return HttpResponse("OK")
        else:
            return HttpResponse("ERROR")
    else:
        return HttpResponseBadRequest("POST Expected.")




