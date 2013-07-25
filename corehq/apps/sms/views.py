#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import logging
from datetime import datetime
import re
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.shortcuts import render
from corehq.apps.api.models import require_api_user_permission, PERMISSION_POST_SMS
from corehq.apps.sms.api import send_sms, incoming, send_sms_with_backend
from corehq.apps.users.models import CouchUser
from corehq.apps.users import models as user_models
from corehq.apps.sms.models import SMSLog, INCOMING, ForwardingRule
from corehq.apps.sms.forms import ForwardingRuleForm
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest, domain_admin_required, require_superuser
from dimagi.utils.couch.database import get_db
from django.contrib import messages
from corehq.apps.reports import util as report_utils
from django.views.decorators.csrf import csrf_exempt

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse(compose_message, args=[domain]))

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
    return render(request, template, context)

@login_and_domain_required
def compose_message(request, domain, template="sms/compose.html"):
    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['now'] = datetime.utcnow()
    tz = report_utils.get_timezone(request.couch_user.user_id, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    return render(request, template, context)

def post(request, domain):
    # TODO: Figure out if this is being used anywhere and remove it if not
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

@require_api_user_permission(PERMISSION_POST_SMS)
def sms_in(request):
    """
    CommCareHQ's generic inbound sms post api, requiring an ApiUser with permission to post sms.
    The request must be a post, and must have the following post parameters:
        username - ApiUser username
        password - ApiUser password
        phone_number - phone number message was sent from
        message - text of message
    """
    backend_api = "HQ_HTTP_INBOUND"
    phone_number = request.POST.get("phone_number", None)
    message = request.POST.get("message", None)
    if phone_number is None or message is None:
        return HttpResponse("Please specify 'phone_number' and 'message' parameters.", status=400)
    else:
        incoming(phone_number, message, backend_api)
        return HttpResponse("OK")

def get_sms_autocomplete_context(request, domain):
    """A helper view for sms autocomplete"""
    phone_users = CouchUser.view("users/phone_users_by_domain",
        startkey=[domain], endkey=[domain, {}], include_docs=True
    )
    groups = Group.view("groups/by_domain", key=domain, include_docs=True)

    contacts = ["[send to all]"]
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
        send_to_all_checked = False

        for recipient in recipients:
            if recipient == "[send to all]":
                send_to_all_checked = True
                phone_users = CouchUser.view("users/phone_users_by_domain",
                    startkey=[domain], endkey=[domain, {}], include_docs=True
                )
                for user in phone_users:
                    usernames.append(user.username)
                group_names = []
                break
            elif (not send_to_all_checked) and recipient.endswith(GROUP):
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
            elif (not send_to_all_checked) and re.match(r'[\w\.]+', recipient):
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

@domain_admin_required
def message_test(request, domain, phone_number):
    if request.method == "POST":
        message = request.POST.get("message", "")
        domain_scope = None if request.couch_user.is_superuser else domain
        incoming(phone_number, message, "TEST", domain_scope=domain_scope)

    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['messagelog'] = SMSLog.by_domain_dsc(domain)
    context['now'] = datetime.utcnow()
    tz = report_utils.get_timezone(request.couch_user.user_id, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    context['layout_flush_content'] = True
    context['phone_number'] = phone_number
    return render(request, "sms/message_tester.html", context)

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

@login_and_domain_required
@require_superuser
def list_forwarding_rules(request, domain):
    forwarding_rules = ForwardingRule.view("sms/forwarding_rule", key=[domain], include_docs=True).all()
    
    context = {
        "domain" : domain,
        "forwarding_rules" : forwarding_rules,
    }
    return render(request, "sms/list_forwarding_rules.html", context)

@login_and_domain_required
@require_superuser
def add_forwarding_rule(request, domain, forwarding_rule_id=None):
    forwarding_rule = None
    if forwarding_rule_id is not None:
        forwarding_rule = ForwardingRule.get(forwarding_rule_id)
        if forwarding_rule.domain != domain:
            raise Http404
    
    if request.method == "POST":
        form = ForwardingRuleForm(request.POST)
        if form.is_valid():
            if forwarding_rule is None:
                forwarding_rule = ForwardingRule(domain=domain)
            forwarding_rule.forward_type = form.cleaned_data.get("forward_type")
            forwarding_rule.keyword = form.cleaned_data.get("keyword")
            forwarding_rule.backend_id = form.cleaned_data.get("backend_id")
            forwarding_rule.save()
            return HttpResponseRedirect(reverse('list_forwarding_rules', args=[domain]))
    else:
        initial = {}
        if forwarding_rule is not None:
            initial["forward_type"] = forwarding_rule.forward_type
            initial["keyword"] = forwarding_rule.keyword
            initial["backend_id"] = forwarding_rule.backend_id
        form = ForwardingRuleForm(initial=initial)
    
    context = {
        "domain" : domain,
        "form" : form,
        "forwarding_rule_id" : forwarding_rule_id,
    }
    return render(request, "sms/add_forwarding_rule.html", context)

@login_and_domain_required
@require_superuser
def delete_forwarding_rule(request, domain, forwarding_rule_id):
    forwarding_rule = ForwardingRule.get(forwarding_rule_id)
    if forwarding_rule.domain != domain:
        raise Http404
    forwarding_rule.retire()
    return HttpResponseRedirect(reverse("list_forwarding_rules", args=[domain]))

