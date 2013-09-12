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
from corehq.apps.sms.api import send_sms, incoming, send_sms_with_backend_name
from corehq.apps.users.models import CouchUser
from corehq.apps.users import models as user_models
from corehq.apps.sms.models import SMSLog, INCOMING, ForwardingRule
from corehq.apps.sms.mixin import MobileBackend, SMSBackend, BackendMapping
from corehq.apps.sms.forms import ForwardingRuleForm, BackendMapForm
from corehq.apps.sms.util import get_available_backends
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest, domain_admin_required, require_superuser
from dimagi.utils.couch.database import get_db
from django.contrib import messages
from corehq.apps.reports import util as report_utils
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.domain.models import Domain
from django.utils.translation import ugettext as _, ugettext_noop

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
        messages.error(request, _("You didn't specify any recipients"))
    elif not message:
        messages.error(request, _("You can't send an empty message"))
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
                messages.error(request, _("The following groups don't exist: ") + (', '.join(empty_groups)))
            if no_numbers:
                messages.error(request, _("The following users don't have phone numbers: ") + (', '.join(no_numbers)))
            if failed_numbers:
                messages.error(request, _("Couldn't send to the following number(s): ") + (', '.join(failed_numbers)))
            if unknown_usernames:
                messages.error(request, _("Couldn't find the following user(s): ") + (', '.join(unknown_usernames)))
            if sent:
                messages.success(request, _("Successfully sent: ") + (', '.join(sent)))
            else:
                messages.info(request, _("No messages were sent."))
        else:
            messages.success(request, _("Message sent"))

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
    """
    An API to send SMS.
    Expected post parameters:
        phone_number - the phone number to send to
        text - the text of the message
        backend_id - the name of the MobileBackend to use while sending
    """
    if request.method == "POST":
        phone_number = request.POST.get("phone_number", None)
        text = request.POST.get("text", None)
        backend_id = request.POST.get("backend_id", None)
        if (phone_number is None) or (text is None) or (backend_id is None):
            return HttpResponseBadRequest("Not enough arguments.")
        if send_sms_with_backend_name(domain, phone_number, text, backend_id):
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
    if forwarding_rule.domain != domain or forwarding_rule.doc_type != "ForwardingRule":
        raise Http404
    forwarding_rule.retire()
    return HttpResponseRedirect(reverse("list_forwarding_rules", args=[domain]))

def _add_backend(request, backend_class_name, is_global, domain=None, backend_id=None):
    # We can remove this restriction once we implement throttling of http backends, and billing for domain-specific backends
    if not (request.couch_user.is_superuser or is_global or backend_class_name == "TelerivetBackend"):
        raise Http404
    backend_classes = get_available_backends()
    backend_class = backend_classes[backend_class_name]
    
    backend = None
    if backend_id is not None:
        backend = backend_class.get(backend_id)
        if not is_global and backend.domain != domain:
            raise Http404
    
    ignored_fields = ["give_other_domains_access"]
    if request.method == "POST":
        form = backend_class.get_form_class()(request.POST)
        form._cchq_domain = domain
        form._cchq_backend_id = backend._id if backend is not None else None
        if form.is_valid():
            if backend is None:
                backend = backend_class(domain=domain, is_global=is_global)
            for key, value in form.cleaned_data.items():
                if key not in ignored_fields:
                    setattr(backend, key, value)
            backend.save()
            if is_global:
                return HttpResponseRedirect(reverse("list_backends"))
            else:
                return HttpResponseRedirect(reverse("list_domain_backends", args=[domain]))
    else:
        initial = {}
        if backend is not None:
            for field in backend_class.get_form_class()():
                if field.name not in ignored_fields:
                    if field.name == "authorized_domains":
                        initial[field.name] = ",".join(backend.authorized_domains)
                    else:
                        initial[field.name] = getattr(backend, field.name, None)
            if len(backend.authorized_domains) > 0:
                initial["give_other_domains_access"] = True
            else:
                initial["give_other_domains_access"] = False
        form = backend_class.get_form_class()(initial=initial)
    context = {
        "is_global" : is_global,
        "domain" : domain,
        "form" : form,
        "backend_class_name" : backend_class_name,
        "backend_generic_name" : backend_class.get_generic_name(),
        "backend_id" : backend_id,
    }
    return render(request, backend_class.get_template(), context)

@domain_admin_required
def add_domain_backend(request, domain, backend_class_name, backend_id=None):
    return _add_backend(request, backend_class_name, False, domain, backend_id)

@require_superuser
def add_backend(request, backend_class_name, backend_id=None):
    return _add_backend(request, backend_class_name, True, backend_id=backend_id)

def _list_backends(request, show_global=False, domain=None):
    backend_classes = get_available_backends()
    backends = []
    editable_backend_ids = []
    default_sms_backend_id = None
    if not show_global:
        domain_obj = Domain.get_by_name(domain, strict=True)
    raw_backends = []
    if not show_global:
        raw_backends += SMSBackend.view("sms/backend_by_domain", classes=backend_classes,
                                        startkey=[domain], endkey=[domain, {}], include_docs=True).all()
        if len(raw_backends) > 0 and domain_obj.default_sms_backend_id in [None, ""]:
            messages.error(request, _("WARNING: You have not specified a default SMS connection. By default, the system will automatically select one of the SMS connections owned by the system when sending sms."))
    raw_backends += SMSBackend.view("sms/global_backends", classes=backend_classes, include_docs=True).all()
    for backend in raw_backends:
        backends.append(backend_classes[backend.doc_type].wrap(backend.to_json()))
        if show_global or (not backend.is_global and backend.domain == domain):
            editable_backend_ids.append(backend._id)
        if not show_global and domain_obj.default_sms_backend_id == backend._id:
            default_sms_backend_id = backend._id
    instantiable_backends = []
    for name, klass in backend_classes.items():
        try:
            assert request.couch_user.is_superuser or show_global or name == "TelerivetBackend" # TODO: Remove this once domain-specific billing is sorted out
            klass.get_generic_name()
            klass.get_form_class()
            instantiable_backends.append((name, klass))
        except Exception:
            pass
    instantiable_backends.sort(key = lambda t : t[0])
    context = {
        "show_global" : show_global,
        "domain" : domain,
        "backends" : backends,
        "editable_backend_ids" : editable_backend_ids,
        "default_sms_backend_id" : default_sms_backend_id,
        "instantiable_backends" : instantiable_backends,
    }
    return render(request, "sms/list_backends.html", context)

@domain_admin_required
def list_domain_backends(request, domain):
    return _list_backends(request, False, domain)

@require_superuser
def list_backends(request):
    return _list_backends(request, True)

@require_superuser
def default_sms_admin_interface(request):
    return HttpResponseRedirect(reverse("list_backends"))

@domain_admin_required
def delete_domain_backend(request, domain, backend_id):
    backend = SMSBackend.get(backend_id)
    if backend.domain != domain or backend.base_doc != "MobileBackend":
        raise Http404
    domain_obj = Domain.get_by_name(domain, strict=True)
    if domain_obj.default_sms_backend_id == backend._id:
        domain_obj.default_sms_backend_id = None
        domain_obj.save()
    backend.retire() # Do not actually delete so that linkage always exists between SMSLog and MobileBackend
    return HttpResponseRedirect(reverse("list_domain_backends", args=[domain]))

@require_superuser
def delete_backend(request, backend_id):
    backend = SMSBackend.get(backend_id)
    if not backend.is_global or backend.base_doc != "MobileBackend":
        raise Http404
    backend.retire() # Do not actually delete so that linkage always exists between SMSLog and MobileBackend
    return HttpResponseRedirect(reverse("list_backends"))

def _set_default_domain_backend(request, domain, backend_id, unset=False):
    backend = SMSBackend.get(backend_id)
    if not backend.domain_is_authorized(domain):
        raise Http404
    domain_obj = Domain.get_by_name(domain, strict=True)
    domain_obj.default_sms_backend_id = None if unset else backend._id
    domain_obj.save()
    return HttpResponseRedirect(reverse("list_domain_backends", args=[domain]))

@domain_admin_required
def set_default_domain_backend(request, domain, backend_id):
    return _set_default_domain_backend(request, domain, backend_id)

@domain_admin_required
def unset_default_domain_backend(request, domain, backend_id):
    return _set_default_domain_backend(request, domain, backend_id, True)

@require_superuser
def global_backend_map(request):
    backend_classes = get_available_backends()
    global_backends = SMSBackend.view("sms/global_backends", classes=backend_classes, include_docs=True).all()
    current_map = {}
    catchall_entry = None
    for entry in BackendMapping.view("sms/backend_map", startkey=["*"], endkey=["*", {}], include_docs=True).all():
        if entry.prefix == "*":
            catchall_entry = entry
        else:
            current_map[entry.prefix] = entry
    if request.method == "POST":
        form = BackendMapForm(request.POST)
        if form.is_valid():
            new_backend_map = form.cleaned_data.get("backend_map")
            new_catchall_backend_id = form.cleaned_data.get("catchall_backend_id")
            for prefix, entry in current_map.items():
                if prefix not in new_backend_map:
                    current_map[prefix].delete()
                    del current_map[prefix]
            for prefix, backend_id in new_backend_map.items():
                if prefix in current_map:
                    current_map[prefix].backend_id = backend_id
                    current_map[prefix].save()
                else:
                    current_map[prefix] = BackendMapping(is_global=True, prefix=prefix, backend_id=backend_id)
                    current_map[prefix].save()
            if new_catchall_backend_id is None:
                if catchall_entry is not None:
                    catchall_entry.delete()
                    catchall_entry = None
            else:
                if catchall_entry is None:
                    catchall_entry = BackendMapping(is_global=True, prefix="*", backend_id=new_catchall_backend_id)
                else:
                    catchall_entry.backend_id = new_catchall_backend_id
                catchall_entry.save()
            messages.success(request, _("Changes Saved."))
    else:
        initial = {
            "catchall_backend_id" : catchall_entry.backend_id if catchall_entry is not None else None,
            "backend_map" : [{"prefix" : prefix, "backend_id" : entry.backend_id} for prefix, entry in current_map.items()],
        }
        form = BackendMapForm(initial=initial)
    context = {
        "backends" : global_backends,
        "form" : form,
    }
    return render(request, "sms/backend_map.html", context)

