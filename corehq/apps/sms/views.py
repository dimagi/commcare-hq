#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
import logging
from datetime import datetime, timedelta, time
import re
import json
import pytz
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from corehq.apps.api.models import require_api_user_permission, PERMISSION_POST_SMS
from corehq.apps.sms.api import (
    send_sms,
    incoming,
    send_sms_with_backend_name,
    send_sms_to_verified_number,
    DomainScopeValidationError,
)
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CouchUser, Permissions
from corehq.apps.users import models as user_models
from corehq.apps.users.views.mobile.users import EditCommCareUserView
from corehq.apps.sms.models import SMSLog, INCOMING, OUTGOING, ForwardingRule, CommConnectCase
from corehq.apps.sms.mixin import MobileBackend, SMSBackend, BackendMapping, VerifiedNumber
from corehq.apps.sms.forms import ForwardingRuleForm, BackendMapForm, InitiateAddSMSBackendForm, SMSSettingsForm
from corehq.apps.sms.util import get_available_backends, get_contact
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import login_and_domain_required, login_or_digest, domain_admin_required, require_superuser
from dimagi.utils.couch.database import get_db
from django.contrib import messages
from corehq.apps.reports import util as report_utils
from dimagi.utils.timezones import utils as tz_utils
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.domain.models import Domain
from django.utils.translation import ugettext as _, ugettext_noop
from couchdbkit.resource import ResourceNotFound
from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_datetime, string_to_boolean
from dateutil.parser import parse
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception
from django.conf import settings

DEFAULT_MESSAGE_COUNT_THRESHOLD = 50

# Tuple of (description, days in the past)
SMS_CHAT_HISTORY_CHOICES = (
    (ugettext_noop("Yesterday"), 1),
    (ugettext_noop("1 Week"), 7),
    (ugettext_noop("30 Days"), 30),
)

@login_and_domain_required
def default(request, domain):
    return HttpResponseRedirect(reverse(compose_message, args=[domain]))


class BaseMessagingSectionView(BaseDomainView):
    section_name = ugettext_noop("Messaging")

    @property
    def section_url(self):
        return reverse("sms_default", args=[self.domain])


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
            elif send_sms(domain, user, number, message):
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
        try:
            incoming(phone_number, message, "TEST", domain_scope=domain_scope)
        except DomainScopeValidationError:
            messages.error(
                request,
                _("Invalid phone number being simulated. You may only " \
                  "simulate SMS from verified numbers belonging to contacts " \
                  "in this domain.")
            )
        except Exception:
            notify_exception(request)
            messages.error(
                request,
                _("An error has occurred. Please try again in a few minutes " \
                  "and if the issue persists, please contact CommCareHQ " \
                  "Support.")
            )

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
        contact_id - the _id of a contact to send to (overrides phone_number)
        text - the text of the message
        backend_id - the name of the MobileBackend to use while sending
    """
    if request.method == "POST":
        phone_number = request.POST.get("phone_number", None)
        contact_id = request.POST.get("contact_id", None)
        text = request.POST.get("text", None)
        backend_id = request.POST.get("backend_id", None)
        chat = request.POST.get("chat", None)

        if (phone_number is None and contact_id is None) or (text is None):
            return HttpResponseBadRequest("Not enough arguments.")

        vn = None
        if contact_id is not None:
            try:
                contact = get_contact(contact_id)
                assert contact is not None
                assert contact.domain == domain
            except Exception:
                return HttpResponseBadRequest("Contact not found.")
            try:
                vn = contact.get_verified_number()
                assert vn is not None
                phone_number = vn.phone_number
            except Exception:
                return HttpResponseBadRequest("Contact has no phone number.")

        try:
            chat_workflow = string_to_boolean(chat)
        except Exception:
            chat_workflow = False

        if chat_workflow:
            chat_user_id = request.couch_user._id
        else:
            chat_user_id = None

        if backend_id is not None:
            success = send_sms_with_backend_name(domain, phone_number, text, backend_id, chat_user_id=chat_user_id)
        elif vn is not None:
            success = send_sms_to_verified_number(vn, text, chat_user_id=chat_user_id)
        else:
            success = send_sms(domain, None, phone_number, text, chat_user_id=chat_user_id)

        if success:
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
        raw_backends += SMSBackend.view(
            "sms/backend_by_domain",
            reduce=False,
            classes=backend_classes,
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()
        if len(raw_backends) > 0 and domain_obj.default_sms_backend_id in [None, ""]:
            messages.error(request, _("WARNING: You have not specified a default SMS connection. By default, the system will automatically select one of the SMS connections owned by the system when sending sms."))
    raw_backends += SMSBackend.view(
        "sms/global_backends",
        classes=backend_classes,
        include_docs=True,
        reduce=False
    ).all()
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
    global_backends = SMSBackend.view(
        "sms/global_backends",
        classes=backend_classes,
        include_docs=True,
        reduce=False
    ).all()
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

@require_permission(Permissions.edit_data)
def chat_contacts(request, domain):
    domain_obj = Domain.get_by_name(domain, strict=True)
    verified_numbers = VerifiedNumber.by_domain(domain)
    contacts = []
    for vn in verified_numbers:
        owner = vn.owner
        if owner is not None and owner.doc_type in ('CommCareCase','CommCareUser'):
            if owner.doc_type == "CommCareUser":
                url = reverse(EditCommCareUserView.urlname, args=[domain, owner._id])
                name = owner.raw_username
            else:
                url = reverse("case_details", args=[domain, owner._id])
                if domain_obj.custom_case_username:
                    name = owner.get_case_property(domain_obj.custom_case_username) or _("(unknown)")
                else:
                    name = owner.name
            contacts.append({
                "id" : owner._id,
                "doc_type" : owner.doc_type,
                "url" : url,
                "name" : name,
            })
    context = {
        "domain" : domain,
        "contacts" : contacts,
    }
    return render(request, "sms/chat_contacts.html", context)

@require_permission(Permissions.edit_data)
def chat(request, domain, contact_id):
    domain_obj = Domain.get_by_name(domain, strict=True)
    timezone = report_utils.get_timezone(None, domain)

    # floored_utc_timestamp is the datetime in UTC representing
    # midnight today in local time. This is used to calculate
    # all message history choices' timestamps, so that choosing
    # "Yesterday", for example, gives you data from yesterday at
    # midnight local time.
    local_date = datetime.now(timezone).date()
    floored_utc_timestamp = tz_utils.adjust_datetime_to_timezone(
        datetime.combine(local_date, time(0,0)),
        timezone.zone,
        pytz.utc.zone
    ).replace(tzinfo=None)

    def _fmt(d):
        return json_format_datetime(floored_utc_timestamp - timedelta(days=d))
    history_choices = [(_(x), _fmt(y)) for (x, y) in SMS_CHAT_HISTORY_CHOICES]
    history_choices.append(
        (_("All Time"), json_format_datetime(datetime(1970, 1, 1)))
    )

    context = {
        "domain" : domain,
        "contact_id" : contact_id,
        "contact" : get_contact(contact_id),
        "message_count_threshold" : domain_obj.chat_message_count_threshold or DEFAULT_MESSAGE_COUNT_THRESHOLD,
        "custom_case_username" : domain_obj.custom_case_username,
        "history_choices" : history_choices,
    }
    template = settings.CUSTOM_CHAT_TEMPLATES.get(domain_obj.custom_chat_template) or "sms/chat.html"
    return render(request, template, context)

@require_permission(Permissions.edit_data)
def api_history(request, domain):
    result = []
    contact_id = request.GET.get("contact_id", None)
    start_date = request.GET.get("start_date", None)
    timezone = report_utils.get_timezone(None, domain)
    domain_obj = Domain.get_by_name(domain, strict=True)

    try:
        assert contact_id is not None
        doc = get_contact(contact_id)
        assert doc is not None
        assert doc.domain == domain
    except Exception:
        return HttpResponse("[]")

    query_start_date_str = None
    if start_date is not None:
        try:
            query_start_date = parse(start_date)
            query_start_date += timedelta(seconds=1)
            query_start_date_str = json_format_datetime(query_start_date)
        except Exception:
            pass

    if query_start_date_str is not None:
        data = SMSLog.view("sms/by_recipient",
                           startkey=[doc.doc_type, contact_id, "SMSLog", INCOMING, query_start_date_str],
                           endkey=[doc.doc_type, contact_id, "SMSLog", INCOMING, {}],
                           include_docs=True,
                           reduce=False).all()
        data += SMSLog.view("sms/by_recipient",
                            startkey=[doc.doc_type, contact_id, "SMSLog", OUTGOING, query_start_date_str],
                            endkey=[doc.doc_type, contact_id, "SMSLog", OUTGOING, {}],
                            include_docs=True,
                            reduce=False).all()
    else:
        data = SMSLog.view("sms/by_recipient",
                           startkey=[doc.doc_type, contact_id, "SMSLog"],
                           endkey=[doc.doc_type, contact_id, "SMSLog", {}],
                           include_docs=True,
                           reduce=False).all()
    data.sort(key=lambda x : x.date)
    username_map = {}
    for sms in data:
        if sms.direction == INCOMING:
            if doc.doc_type == "CommCareCase" and domain_obj.custom_case_username:
                sender = doc.get_case_property(domain_obj.custom_case_username)
            elif doc.doc_type == "CommCareCase":
                sender = doc.name
            else:
                sender = doc.first_name or doc.raw_username
        elif sms.chat_user_id is not None:
            if sms.chat_user_id in username_map:
                sender = username_map[sms.chat_user_id]
            else:
                try:
                    user = CouchUser.get_by_user_id(sms.chat_user_id)
                    sender = user.first_name or user.raw_username
                except Exception:
                    sender = _("Unknown")
                username_map[sms.chat_user_id] = sender
        else:
            sender = _("System")
        result.append({
            "sender" : sender,
            "text" : sms.text,
            "timestamp" : tz_utils.adjust_datetime_to_timezone(sms.date, pytz.utc.zone, timezone.zone).strftime("%I:%M%p %m/%d/%y").lower(),
            "utc_timestamp" : json_format_datetime(sms.date),
        })
    return HttpResponse(json.dumps(result))

class DomainSmsGatewayListView(CRUDPaginatedViewMixin, BaseMessagingSectionView):
    template_name = "sms/gateway_list.html"
    urlname = 'list_domain_backends_new'
    page_title = ugettext_noop("SMS Connectivity")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        domain_backends = SMSBackend.get_db().view(
            "sms/backend_by_domain",
            startkey=[self.domain],
            endkey=[self.domain, {}],
            reduce=True,
        ).first() or {}
        global_backends = SMSBackend.get_db().view(
            'sms/global_backends',
            reduce=True,
        ).first() or {}
        return domain_backends.get('value', 0) + global_backends.get('value', 0)

    @property
    def column_names(self):
        return [
            _("Connection"),
            _("Default"),
        ]

    @property
    def page_context(self):
        context = self.pagination_context
        context.update({
            'initiate_new_form': InitiateAddSMSBackendForm(is_superuser=self.request.couch_user.is_superuser),
        })
        return context

    @property
    def paginated_list(self):
        all_backends = []
        all_backends += SMSBackend.view(
            "sms/backend_by_domain",
            classes=self.backend_classes,
            startkey=[self.domain],
            endkey=[self.domain, {}],
            reduce=False,
            include_docs=True
        ).all()
        all_backends += SMSBackend.view(
            'sms/global_backends',
            classes=self.backend_classes,
            reduce=False,
            include_docs=True
        ).all()

        if len(all_backends) > 0 and not self.domain_object.default_sms_backend_id:
            yield {
                'itemData': {
                    'id': 'nodefault',
                    'name': "Automatic Choose",
                    'status': 'DEFAULT',
                },
                'template': 'gateway-automatic-template',
            }
        elif self.domain_object.default_sms_backend_id:
            default_backend = SMSBackend.get(self.domain_object.default_sms_backend_id)
            yield {
                'itemData': self._fmt_backend_data(default_backend),
                'template': 'gateway-default-template',
            }
        for backend in all_backends:
            if not backend._id == self.domain_object.default_sms_backend_id:
                yield {
                    'itemData': self._fmt_backend_data(backend),
                    'template': 'gateway-template',
                }

    @property
    @memoized
    def backend_classes(self):
        return get_available_backends()

    def _fmt_backend_data(self, backend):
        return {
            'id': backend._id,
            'name': backend.name,
            'editUrl': reverse(
                'edit_domain_backend',
                args=[self.domain, backend.__class__.__name__, backend._id]
            ) if not backend.is_global else "",
        }

    def refresh_item(self, item_id):
        if self.domain_object.default_sms_backend_id == item_id:
            self.domain_object.default_sms_backend_id = None
        else:
            self.domain_object.default_sms_backend_id = item_id
        self.domain_object.save()

    @property
    def allowed_actions(self):
        actions = super(DomainSmsGatewayListView, self).allowed_actions
        return actions + ['new_backend']

    def post(self, request, *args, **kwargs):
        if self.action == 'new_backend':
            backend_type = request.POST['backend_type']
            return HttpResponseRedirect(reverse('add_domain_backend', args=[self.domain, backend_type]))
        return self.paginate_crud_response

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(DomainSmsGatewayListView, self).dispatch(request, *args, **kwargs)

@domain_admin_required
def sms_settings(request, domain):
    domain_obj = Domain.get_by_name(domain, strict=True)
    is_previewer = request.couch_user.is_previewer()
    if request.method == "POST":
        form = SMSSettingsForm(request.POST)
        form._cchq_is_previewer = is_previewer
        if form.is_valid():
            domain_obj.use_default_sms_response = form.cleaned_data["use_default_sms_response"]
            domain_obj.default_sms_response = form.cleaned_data["default_sms_response"]
            if is_previewer:
                domain_obj.custom_case_username = form.cleaned_data["custom_case_username"]
                domain_obj.chat_message_count_threshold = form.cleaned_data["custom_message_count_threshold"]
                domain_obj.custom_chat_template = form.cleaned_data["custom_chat_template"]
            domain_obj.save()
            messages.success(request, _("Changes Saved."))
    else:
        initial = {
            "use_default_sms_response" : domain_obj.use_default_sms_response,
            "default_sms_response" : domain_obj.default_sms_response,
            "use_custom_case_username" : domain_obj.custom_case_username is not None,
            "custom_case_username" : domain_obj.custom_case_username,
            "use_custom_message_count_threshold" : domain_obj.chat_message_count_threshold is not None,
            "custom_message_count_threshold" : domain_obj.chat_message_count_threshold,
            "use_custom_chat_template" : domain_obj.custom_chat_template is not None,
            "custom_chat_template" : domain_obj.custom_chat_template,
        }
        form = SMSSettingsForm(initial=initial)

    context = {
        "domain" : domain,
        "form" : form,
        "is_previewer" : is_previewer,
    }
    return render(request, "sms/settings.html", context)

