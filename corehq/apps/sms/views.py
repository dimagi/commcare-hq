#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from StringIO import StringIO
import logging
from datetime import datetime, timedelta, time
import re
import json
from couchdbkit import ResourceNotFound
import pytz
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from casexml.apps.case.models import CommCareCase
from corehq import privileges
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.reminders.util import can_use_survey_reminders
from corehq.apps.accounting.decorators import requires_privilege_with_fallback, requires_privilege_plaintext_response
from corehq.apps.api.models import require_api_user_permission, PERMISSION_POST_SMS
from corehq.apps.commtrack.models import AlertConfig
from corehq.apps.sms.api import (
    send_sms,
    incoming,
    send_sms_with_backend_name,
    send_sms_to_verified_number,
    DomainScopeValidationError,
    MessageMetadata,
)
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.sms.dbaccessors import get_forwarding_rules_for_domain
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CouchUser, Permissions, CommCareUser
from corehq.apps.users import models as user_models
from corehq.apps.users.views.mobile.users import EditCommCareUserView
from corehq.apps.sms.models import (
    SMSLog, INCOMING, OUTGOING, ForwardingRule,
    LastReadMessage, MessagingEvent
)
from corehq.apps.sms.mixin import (SMSBackend, BackendMapping, VerifiedNumber,
    SMSLoadBalancingMixin)
from corehq.apps.sms.forms import (ForwardingRuleForm, BackendMapForm,
    InitiateAddSMSBackendForm, SubscribeSMSForm,
    SettingsForm, SHOW_ALL, SHOW_INVALID, HIDE_ALL, ENABLED, DISABLED,
    DEFAULT, CUSTOM)
from corehq.apps.sms.util import get_available_backends, get_contact
from corehq.apps.sms.messages import _MESSAGES
from corehq.apps.smsbillables.utils import country_name_from_isd_code_or_empty as country_name_from_code
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest_ex,
    domain_admin_required,
    require_superuser,
)
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.util.dates import iso_string_to_datetime
from corehq.util.spreadsheets.excel import WorkbookJSONReader
from corehq.util.timezones.conversions import ServerTime, UserTime
from dimagi.utils.couch.database import get_db
from django.contrib import messages
from corehq.util.timezones.utils import get_timezone_for_user
from django.views.decorators.csrf import csrf_exempt
from corehq.apps.domain.models import Domain
from django.utils.translation import ugettext as _, ugettext_noop
from dimagi.utils.parsing import json_format_datetime, string_to_boolean
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.decorators.view import get_file
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_response
from dimagi.utils.couch import release_lock
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.couch.cache import cache_core
from django.conf import settings
from couchdbkit.resource import ResourceNotFound
from couchexport.models import Format
from couchexport.export import export_raw
from couchexport.shortcuts import export_response


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

    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, *args, **kwargs):
        return super(BaseMessagingSectionView, self).dispatch(*args, **kwargs)

    @property
    def section_url(self):
        return reverse("sms_default", args=[self.domain])


@login_and_domain_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def messaging(request, domain, template="sms/default.html"):
    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['messagelog'] = SMSLog.by_domain_dsc(domain)
    context['now'] = datetime.utcnow()
    tz = get_timezone_for_user(request.couch_user, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    context['layout_flush_content'] = True
    return render(request, template, context)


@require_permission(Permissions.edit_data)
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def compose_message(request, domain, template="sms/compose.html"):
    context = get_sms_autocomplete_context(request, domain)
    context['domain'] = domain
    context['now'] = datetime.utcnow()
    tz = get_timezone_for_user(request.couch_user, domain)
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
                 date = datetime.utcnow(),
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
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
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
            elif re.match(r'^\+\d+$', recipient): # here we expect it to have a plus sign
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


        login_ids = dict([(r['key'], r['id']) for r in get_db().view("users/by_username", keys=usernames, reduce=False).all()])
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

        if len(phone_numbers) == 1:
            recipient = phone_numbers[0][0]
        else:
            recipient = None

        logged_event = MessagingEvent.create_event_for_adhoc_sms(domain, recipient=recipient)

        for user, number in phone_numbers:
            if not number:
                no_numbers.append(user.raw_username)
            else:
                args = [user.doc_type, user.get_id] if user else []
                logged_subevent = logged_event.create_subevent_for_single_sms(*args)
                if send_sms(
                    domain, user, number, message,
                    metadata=MessageMetadata(messaging_subevent_id=logged_subevent.pk)
                ):
                    sent.append("%s" % (user.raw_username if user else number))
                    logged_subevent.completed()
                else:
                    failed_numbers.append("%s (%s)" % (
                        number,
                        user.raw_username if user else "<no username>"
                    ))
                    logged_subevent.error(MessagingEvent.ERROR_INTERNAL_SERVER_ERROR)

        logged_event.completed()

        def comma_reminder():
            messages.error(request, _("Please remember to separate recipients"
                " with a comma."))

        if empty_groups or failed_numbers or unknown_usernames or no_numbers:
            if empty_groups:
                messages.error(request, _("The following groups don't exist: ") + (', '.join(empty_groups)))
                comma_reminder()
            if no_numbers:
                messages.error(request, _("The following users don't have phone numbers: ") + (', '.join(no_numbers)))
            if failed_numbers:
                messages.error(request, _("Couldn't send to the following number(s): ") + (', '.join(failed_numbers)))
            if unknown_usernames:
                messages.error(request, _("Couldn't find the following user(s): ") + (', '.join(unknown_usernames)))
                comma_reminder()
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
@requires_privilege_with_fallback(privileges.INBOUND_SMS)
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
    tz = get_timezone_for_user(request.couch_user, domain)
    context['timezone'] = tz
    context['timezone_now'] = datetime.now(tz=tz)
    context['layout_flush_content'] = True
    context['phone_number'] = phone_number
    return render(request, "sms/message_tester.html", context)

@csrf_exempt
@login_or_digest_ex(allow_cc_users=True)
@requires_privilege_plaintext_response(privileges.OUTBOUND_SMS)
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
        contact = None

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

        logged_event = MessagingEvent.create_event_for_adhoc_sms(
            domain, recipient=contact,
            content_type=(MessagingEvent.CONTENT_CHAT_SMS if chat_workflow
                else MessagingEvent.CONTENT_API_SMS))

        args = [contact.doc_type, contact.get_id] if contact else []
        logged_subevent = logged_event.create_subevent_for_single_sms(*args)

        metadata = MessageMetadata(
            chat_user_id=chat_user_id,
            messaging_subevent_id=logged_subevent.pk,
        )
        if backend_id is not None:
            success = send_sms_with_backend_name(domain, phone_number, text, backend_id, metadata)
        elif vn is not None:
            success = send_sms_to_verified_number(vn, text, metadata)
        else:
            success = send_sms(domain, None, phone_number, text, metadata)

        if success:
            logged_subevent.completed()
            logged_event.completed()
            return HttpResponse("OK")
        else:
            logged_subevent.error(MessagingEvent.ERROR_INTERNAL_SERVER_ERROR)
            return HttpResponse("ERROR")
    else:
        return HttpResponseBadRequest("POST Expected.")


@login_and_domain_required
@require_superuser
def list_forwarding_rules(request, domain):
    forwarding_rules = get_forwarding_rules_for_domain(domain)

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
    backend_class = None
    backend = None

    if backend_id is not None:
        try:
            backend = SMSBackend.get(backend_id)
        except ResourceNotFound:
            raise Http404
        if backend.doc_type not in backend_classes:
            raise Http404
        backend_class = backend_classes[backend.doc_type]
        backend = backend_class.wrap(backend.to_json())
        if not is_global and backend.domain != domain:
            raise Http404

    if backend_class is None:
        if backend_class_name in backend_classes:
            backend_class = backend_classes[backend_class_name]
        else:
            raise Http404

    use_load_balancing = issubclass(backend_class, SMSLoadBalancingMixin)
    ignored_fields = ["give_other_domains_access", "phone_numbers"]
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
            if use_load_balancing:
                backend.x_phone_numbers = form.cleaned_data["phone_numbers"]
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
            if use_load_balancing:
                initial["phone_numbers"] = json.dumps(
                    [{"phone_number": p} for p in backend.phone_numbers])
        form = backend_class.get_form_class()(initial=initial)
    context = {
        "is_global" : is_global,
        "domain" : domain,
        "form" : form,
        "backend_class_name" : backend_class_name,
        "backend_generic_name" : backend_class.get_generic_name(),
        "backend_id" : backend_id,
        "use_load_balancing": use_load_balancing,
    }
    return render(request, backend_class.get_template(), context)


@require_superuser
def add_backend(request, backend_class_name, backend_id=None):
    # We need to keep this until we move over the admin sms gateway UIs
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


@require_superuser
def list_backends(request):
    # We need to keep this until we move over the admin sms gateway UIs
    return _list_backends(request, True)


@require_superuser
def default_sms_admin_interface(request):
    return HttpResponseRedirect(reverse("list_backends"))


@require_superuser
def delete_backend(request, backend_id):
    # We need to keep this until we move over the admin sms gateway UIs
    backend = SMSBackend.get(backend_id)
    if not backend.is_global or backend.base_doc != "MobileBackend":
        raise Http404
    backend.retire() # Do not actually delete so that linkage always exists between SMSLog and MobileBackend
    return HttpResponseRedirect(reverse("list_backends"))


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
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def chat_contacts(request, domain):
    context = {
        "domain" : domain,
    }
    return render(request, "sms/chat_contacts.html", context)


def get_case_contact_info(domain_obj, case_ids):
    data = {}
    for doc in iter_docs(CommCareCase.get_db(), case_ids):
        if domain_obj.custom_case_username:
            name = doc.get(domain_obj.custom_case_username)
        else:
            name = doc.get('name')
        data[doc['_id']] = [name or _('(unknown)')]
    return data


def get_mobile_worker_contact_info(domain_obj, user_ids):
    data = {}
    for doc in iter_docs(CommCareUser.get_db(), user_ids):
        user = CommCareUser.wrap(doc)
        data[user.get_id] = [user.raw_username]
    return data


def get_contact_info(domain):
    # If the data has been cached, just retrieve it from there
    cache_key = 'sms-chat-contact-list-%s' % domain
    cache_expiration = 30 * 60
    try:
        client = cache_core.get_redis_client()
        cached_data = client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except:
        pass

    verified_number_ids = VerifiedNumber.by_domain(domain, ids_only=True)
    domain_obj = Domain.get_by_name(domain, strict=True)
    case_ids = []
    mobile_worker_ids = []
    data = []
    for doc in iter_docs(VerifiedNumber.get_db(), verified_number_ids):
        owner_id = doc['owner_id']
        if doc['owner_doc_type'] == 'CommCareCase':
            case_ids.append(owner_id)
            data.append([
                None,
                'case',
                doc['phone_number'],
                owner_id,
            ])
        elif doc['owner_doc_type'] == 'CommCareUser':
            mobile_worker_ids.append(owner_id)
            data.append([
                None,
                'mobile_worker',
                doc['phone_number'],
                owner_id,
            ])
    contact_data = get_case_contact_info(domain_obj, case_ids)
    contact_data.update(get_mobile_worker_contact_info(domain_obj, mobile_worker_ids))
    for row in data:
        contact_info = contact_data.get(row[3])
        row[0] = contact_info[0] if contact_info else _('(unknown)')

    # Save the data to the cache for faster lookup next time
    try:
        client.set(cache_key, json.dumps(data))
        client.expire(cache_key, cache_expiration)
    except:
        pass

    return data


def format_contact_data(domain, data):
    for row in data:
        contact_id = row[3]
        if row[1] == 'case':
            row[1] = _('Case')
            row.append(reverse('case_details', args=[domain, contact_id]))
        elif row[1] == 'mobile_worker':
            row[1] = _('Mobile Worker')
            row.append(reverse(EditCommCareUserView.urlname, args=[domain, contact_id]))
        else:
            row.append('#')
        row.append(reverse('sms_chat', args=[domain, contact_id]))


@require_permission(Permissions.edit_data)
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def chat_contact_list(request, domain):
    sEcho = request.GET.get('sEcho')
    iDisplayStart = int(request.GET.get('iDisplayStart'))
    iDisplayLength = int(request.GET.get('iDisplayLength'))
    sSearch = request.GET.get('sSearch', '').strip()

    data = get_contact_info(domain)
    total_records = len(data)

    if sSearch:
        regex = re.compile('^.*%s.*$' % sSearch)
        data = filter(lambda row: regex.match(row[0]) or regex.match(row[2]), data)
    filtered_records = len(data)

    data.sort(key=lambda row: row[0])
    data = data[iDisplayStart:iDisplayStart + iDisplayLength]
    format_contact_data(domain, data)
    result = {
        'sEcho': sEcho,
        'aaData': data,
        'iTotalRecords': total_records,
        'iTotalDisplayRecords': filtered_records,
    }

    return HttpResponse(json.dumps(result))


@require_permission(Permissions.edit_data)
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def chat(request, domain, contact_id):
    domain_obj = Domain.get_by_name(domain, strict=True)
    timezone = get_timezone_for_user(None, domain)

    # floored_utc_timestamp is the datetime in UTC representing
    # midnight today in local time. This is used to calculate
    # all message history choices' timestamps, so that choosing
    # "Yesterday", for example, gives you data from yesterday at
    # midnight local time.
    local_date = datetime.now(timezone).date()
    floored_utc_timestamp = UserTime(
        datetime.combine(local_date, time(0, 0)),
        timezone
    ).server_time().done()

    def _fmt(d):
        return json_format_datetime(floored_utc_timestamp - timedelta(days=d))
    history_choices = [(_(x), _fmt(y)) for (x, y) in SMS_CHAT_HISTORY_CHOICES]
    history_choices.append(
        (_("All Time"), json_format_datetime(datetime(1970, 1, 1)))
    )

    context = {
        "domain": domain,
        "contact_id": contact_id,
        "contact": get_contact(contact_id),
        "use_message_counter": domain_obj.chat_message_count_threshold is not None,
        "message_count_threshold": domain_obj.chat_message_count_threshold or 0,
        "custom_case_username": domain_obj.custom_case_username,
        "history_choices": history_choices,
    }
    template = settings.CUSTOM_CHAT_TEMPLATES.get(domain_obj.custom_chat_template) or "sms/chat.html"
    return render(request, template, context)

@require_permission(Permissions.edit_data)
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def api_history(request, domain):
    result = []
    contact_id = request.GET.get("contact_id", None)
    start_date = request.GET.get("start_date", None)
    timezone = get_timezone_for_user(None, domain)
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
            query_start_date = iso_string_to_datetime(start_date)
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
    last_sms = None
    for sms in data:
        # Don't show outgoing SMS that haven't been processed yet
        if sms.direction == OUTGOING and not sms.processed:
            continue
        # Filter SMS that are tied to surveys if necessary
        if ((domain_obj.filter_surveys_from_chat and 
             sms.xforms_session_couch_id)
            and not
            (domain_obj.show_invalid_survey_responses_in_chat and
             sms.direction == INCOMING and
             sms.invalid_survey_response)):
            continue
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
        last_sms = sms
        result.append({
            "sender": sender,
            "text": sms.text,
            "timestamp": (
                ServerTime(sms.date).user_time(timezone)
                .ui_string("%I:%M%p %m/%d/%y").lower()
            ),
            "utc_timestamp": json_format_datetime(sms.date),
            "sent_by_requester": (sms.chat_user_id == request.couch_user.get_id),
        })
    if last_sms:
        try:
            entry, lock = LastReadMessage.get_locked_obj(
                sms.domain,
                request.couch_user._id,
                sms.couch_recipient,
                create=True
            )
            if (not entry.message_timestamp or
                entry.message_timestamp < last_sms.date):
                entry.message_id = last_sms._id
                entry.message_timestamp = last_sms.date
                entry.save()
            release_lock(lock, True)
        except:
            logging.exception("Could not create/save LastReadMessage for message %s" % last_sms._id)
            # Don't let this block returning of the data
            pass
    return HttpResponse(json.dumps(result))

@require_permission(Permissions.edit_data)
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def api_last_read_message(request, domain):
    contact_id = request.GET.get("contact_id", None)
    domain_obj = Domain.get_by_name(domain, strict=True)
    if domain_obj.count_messages_as_read_by_anyone:
        lrm = LastReadMessage.by_anyone(domain, contact_id)
    else:
        lrm = LastReadMessage.by_user(domain, request.couch_user._id, contact_id)
    result = {
        "message_timestamp" : None,
    }
    if lrm:
        result["message_timestamp"] = json_format_datetime(lrm.message_timestamp)
    return HttpResponse(json.dumps(result))


class DomainSmsGatewayListView(CRUDPaginatedViewMixin, BaseMessagingSectionView):
    template_name = "sms/gateway_list.html"
    urlname = 'list_domain_backends'
    page_title = ugettext_noop("SMS Connectivity")
    strict_domain_fetching = True

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
            _("Description"),
            _("Supported Countries"),
            _("Status"),
            _("Actions"),
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
            default_backend = SMSBackend.get_wrapped(self.domain_object.default_sms_backend_id)
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
        is_editable = not backend.is_global and backend.domain == self.domain
        if len(backend.supported_countries) > 0:
            if backend.supported_countries[0] == '*':
                supported_country_names = _('Multiple%s') % '*'
            else:
                supported_country_names = ', '.join(
                    [_(country_name_from_code(int(c))) for c in backend.supported_countries])
        else:
            supported_country_names = ''
        return {
            'id': backend._id,
            'name': backend.name,
            'description': backend.description,
            'supported_countries': supported_country_names,
            'editUrl': reverse(
                EditDomainGatewayView.urlname,
                args=[self.domain, backend.__class__.__name__, backend._id]
            ) if is_editable else "",
            'canDelete': is_editable,
            'isGlobal': backend.is_global,
            'isShared': not backend.is_global and backend.domain != self.domain,
            'deleteModalId': 'delete_%s' % backend._id,
        }

    def get_deleted_item_data(self, item_id):
        try:
            backend = SMSBackend.get(item_id)
        except ResourceNotFound:
            raise Http404()
        if (backend.is_global or backend.domain != self.domain or
            backend.base_doc != "MobileBackend"):
            raise Http404()
        if self.domain_object.default_sms_backend_id == backend._id:
            self.domain_object.default_sms_backend_id = None
            self.domain_object.save()
        # Do not actually delete so that linkage always exists between SMSLog and MobileBackend
        backend.retire()
        return {
            'itemData': self._fmt_backend_data(backend),
            'template': 'gateway-deleted-template',
        }

    def refresh_item(self, item_id):
        backend = SMSBackend.get_wrapped(item_id)
        if not backend.domain_is_authorized(self.domain):
            raise Http404()
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
            return HttpResponseRedirect(reverse(AddDomainGatewayView.urlname, args=[self.domain, backend_type]))
        return self.paginate_crud_response

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(DomainSmsGatewayListView, self).dispatch(request, *args, **kwargs)


class AddDomainGatewayView(BaseMessagingSectionView):
    urlname = 'add_domain_gateway'
    template_name = 'sms/add_gateway.html'
    page_title = ugettext_noop("Add SMS Connection")

    @property
    def is_superuser(self):
        return self.request.couch_user.is_superuser

    @property
    def backend_class_name(self):
        return self.kwargs.get('backend_class_name')

    @property
    def ignored_fields(self):
        return [
            'give_other_domains_access',
            'phone_numbers',
        ]

    @property
    @memoized
    def backend_class(self):
        # Superusers can create/edit any backend
        # Regular users can only create/edit Telerivet backends for now
        if not self.is_superuser and self.backend_class_name != "TelerivetBackend":
            raise Http404()
        backend_classes = get_available_backends()
        try:
            return backend_classes[self.backend_class_name]
        except KeyError:
            raise Http404()

    @property
    def use_load_balancing(self):
        return issubclass(self.backend_class, SMSLoadBalancingMixin)

    @property
    @memoized
    def backend(self):
        return self.backend_class(domain=self.domain, is_global=False)

    @property
    def page_name(self):
        return _("Add %s Connection") % self.backend_class.get_generic_name()

    @property
    def button_text(self):
        return _("Create %s SMS Connection") % self.backend_class.get_generic_name()

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.backend_class_name])

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        if self.request.method == 'POST':
            form = form_class(self.request.POST, button_text=self.button_text)
            form._cchq_domain = self.domain
            return form
        return form_class(button_text=self.button_text)

    @property
    def page_context(self):
        return {
            'form': self.backend_form,
            'button_text': self.button_text,
            'use_load_balancing': self.use_load_balancing,
        }

    @property
    def parent_pages(self):
        return [{
            'title': DomainSmsGatewayListView.page_title,
            'url': reverse(DomainSmsGatewayListView.urlname, args=[self.domain]),
        }]

    def post(self, request, *args, **kwargs):
        if self.backend_form.is_valid():
            for key, value in self.backend_form.cleaned_data.items():
                if key not in self.ignored_fields:
                    setattr(self.backend, key, value)
            if self.use_load_balancing:
                self.backend.x_phone_numbers = self.backend_form.cleaned_data["phone_numbers"]
            self.backend.save()
            return HttpResponseRedirect(reverse(DomainSmsGatewayListView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)

    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(AddDomainGatewayView, self).dispatch(request, *args, **kwargs)


class EditDomainGatewayView(AddDomainGatewayView):
    urlname = 'edit_domain_gateway'
    page_title = ugettext_noop("Edit SMS Connection")

    @property
    def backend_id(self):
        return self.kwargs['backend_id']

    @property
    @memoized
    def backend(self):
        try:
            backend = self.backend_class.get(self.backend_id)
        except ResourceNotFound:
            raise Http404()
        if backend.is_global or backend.domain != self.domain:
            raise Http404()
        if backend.doc_type != self.backend_class_name:
            raise Http404()
        return backend

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        initial = {}
        for field in form_class():
            if field.name not in self.ignored_fields:
                if field.name == 'authorized_domains':
                    initial[field.name] = ','.join(self.backend.authorized_domains)
                else:
                    initial[field.name] = getattr(self.backend, field.name, None)
            initial['give_other_domains_access'] = len(self.backend.authorized_domains) > 0
            if self.use_load_balancing:
                initial["phone_numbers"] = json.dumps(
                    [{"phone_number": p} for p in self.backend.phone_numbers])
        if self.request.method == 'POST':
            form = form_class(self.request.POST, initial=initial,
                              button_text=self.button_text)
            form._cchq_domain = self.domain
            form._cchq_backend_id = self.backend._id
            return form
        return form_class(initial=initial, button_text=self.button_text)

    @property
    def page_name(self):
        return _("Edit %s Connection") % self.backend_class.get_generic_name()

    @property
    def button_text(self):
        return _("Update %s SMS Connection") % self.backend_class.get_generic_name()

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs=self.kwargs)


class SubscribeSMSView(BaseMessagingSectionView):
    template_name = "sms/subscribe_sms.html"
    urlname = 'subscribe_sms'
    page_title = ugettext_noop("Subscribe SMS")

    @property
    def commtrack_settings(self):
        return Domain.get_by_name(self.domain).commtrack_settings

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
             return SubscribeSMSForm(self.request.POST)

        if self.commtrack_settings and self.commtrack_settings.alert_config:
            alert_config = self.commtrack_settings.alert_config
        else:
            alert_config = AlertConfig()
        initial = {
            'stock_out_facilities': alert_config.stock_out_facilities,
            'stock_out_commodities': alert_config.stock_out_commodities,
            'stock_out_rates': alert_config.stock_out_rates,
            'non_report': alert_config.non_report,
        }

        return SubscribeSMSForm(initial=initial)

    @property
    def page_context(self):
        context = {
            "form": self.form,
            "domain": self.domain,
        }
        return context

    def post(self, request, *args, **kwargs):
        if self.form.is_valid():
            self.form.save(self.commtrack_settings)
            messages.success(request, _("Updated CommCare Supply settings."))
            return HttpResponseRedirect(reverse(SubscribeSMSView.urlname, args=[self.domain]))
        return self.get(request, *args, **kwargs)


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def sms_languages(request, domain):
    with StandaloneTranslationDoc.get_locked_obj(domain, "sms",
        create=True) as tdoc:
        if len(tdoc.langs) == 0:
            tdoc.langs = ["en"]
            tdoc.translations["en"] = {}
            tdoc.save()
    context = {
        "domain": domain,
        "sms_langs": tdoc.langs,
        "bulk_upload": {
            "action": reverse("upload_sms_translations",
                              args=(domain,)),
            "download_url": reverse("download_sms_translations",
                                    args=(domain,)),
            "adjective": _("messaging translation"),
            "plural_noun": _("messaging translations"),
        },
    }
    context.update({
        "bulk_upload_form": get_bulk_upload_form(context),
    })

    return render(request, "sms/languages.html", context)


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def edit_sms_languages(request, domain):
    """
    Accepts same post body as corehq.apps.app_manager.views.edit_app_langs
    """
    with StandaloneTranslationDoc.get_locked_obj(domain, "sms",
        create=True) as tdoc:
        try:
            from corehq.apps.app_manager.views import validate_langs
            langs, rename, build = validate_langs(request, tdoc.langs,
                validate_build=False)
        except AssertionError:
            return HttpResponse(status=400)

        for old, new in rename.items():
            if old != new:
                tdoc.translations[new] = tdoc.translations[old]
                del tdoc.translations[old]

        for lang in langs:
            if lang not in tdoc.translations:
                tdoc.translations[lang] = {}

        for lang in tdoc.translations.keys():
            if lang not in langs:
                del tdoc.translations[lang]

        tdoc.langs = langs
        tdoc.save()
        return json_response(langs)


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def download_sms_translations(request, domain):
    tdoc = StandaloneTranslationDoc.get_obj(domain, "sms")
    columns = ["property"] + tdoc.langs + ["default"]

    msg_ids = sorted(_MESSAGES.keys())
    rows = []
    for msg_id in msg_ids:
        rows.append([msg_id])

    for lang in tdoc.langs:
        for row in rows:
            row.append(tdoc.translations[lang].get(row[0], ""))

    for row in rows:
        row.append(_MESSAGES.get(row[0]))

    temp = StringIO()
    headers = (("translations", tuple(columns)),)
    data = (("translations", tuple(rows)),)
    export_raw(headers, data, temp)
    return export_response(temp, Format.XLS_2007, "translations")


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
@get_file("bulk_upload_file")
def upload_sms_translations(request, domain):
    try:
        workbook = WorkbookJSONReader(request.file)
        translations = workbook.get_worksheet(title='translations')

        with StandaloneTranslationDoc.get_locked_obj(domain, "sms") as tdoc:
            msg_ids = sorted(_MESSAGES.keys())
            result = {}
            for lang in tdoc.langs:
                result[lang] = {}

            for row in translations:
                for lang in tdoc.langs:
                    if row.get(lang):
                        msg_id = row["property"]
                        if msg_id in msg_ids:
                            val = row[lang]
                            if not isinstance(val, basestring):
                                val = str(val)
                            val = val.strip()
                            result[lang][msg_id] = val

            tdoc.translations = result
            tdoc.save()
        messages.success(request, _("SMS Translations Updated."))
    except Exception:
        notify_exception(request, 'SMS Upload Translations Error')
        messages.error(request, _("Update failed. We're looking into it."))

    return HttpResponseRedirect(reverse('sms_languages', args=[domain]))


class SMSSettingsView(BaseMessagingSectionView):
    urlname = "sms_settings"
    template_name = "sms/settings.html"
    page_title = ugettext_noop("SMS Settings")

    @property
    def page_name(self):
        return _("SMS Settings")

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    @memoized
    def previewer(self):
        return self.request.couch_user.is_previewer()

    @property
    @memoized
    def form(self):
        if self.request.method == "POST":
            form = SettingsForm(self.request.POST, cchq_domain=self.domain,
                cchq_is_previewer=self.previewer)
        else:
            domain_obj = Domain.get_by_name(self.domain, strict=True)
            enabled_disabled = lambda b: (ENABLED if b else DISABLED)
            default_custom = lambda b: (CUSTOM if b else DEFAULT)
            initial = {
                "use_default_sms_response":
                    enabled_disabled(domain_obj.use_default_sms_response),
                "default_sms_response":
                    domain_obj.default_sms_response,
                "use_restricted_sms_times":
                    enabled_disabled(len(domain_obj.restricted_sms_times) > 0),
                "restricted_sms_times_json":
                    [w.to_json() for w in domain_obj.restricted_sms_times],
                "send_to_duplicated_case_numbers":
                    enabled_disabled(domain_obj.send_to_duplicated_case_numbers),
                "use_custom_case_username":
                    default_custom(domain_obj.custom_case_username),
                "custom_case_username":
                    domain_obj.custom_case_username,
                "use_custom_message_count_threshold":
                    default_custom(
                        domain_obj.chat_message_count_threshold is not None),
                "custom_message_count_threshold":
                    domain_obj.chat_message_count_threshold,
                "use_sms_conversation_times":
                    enabled_disabled(len(domain_obj.sms_conversation_times) > 0),
                "sms_conversation_times_json":
                    [w.to_json() for w in domain_obj.sms_conversation_times],
                "sms_conversation_length":
                    domain_obj.sms_conversation_length,
                "survey_traffic_option":
                    (SHOW_ALL
                     if not domain_obj.filter_surveys_from_chat else
                     SHOW_INVALID
                     if domain_obj.show_invalid_survey_responses_in_chat else
                     HIDE_ALL),
                "count_messages_as_read_by_anyone":
                    enabled_disabled(domain_obj.count_messages_as_read_by_anyone),
                "use_custom_chat_template":
                    default_custom(domain_obj.custom_chat_template),
                "custom_chat_template":
                    domain_obj.custom_chat_template,
                "sms_case_registration_enabled":
                    enabled_disabled(domain_obj.sms_case_registration_enabled),
                "sms_case_registration_type":
                    domain_obj.sms_case_registration_type,
                "sms_case_registration_owner_id":
                    domain_obj.sms_case_registration_owner_id,
                "sms_case_registration_user_id":
                    domain_obj.sms_case_registration_user_id,
                "sms_mobile_worker_registration_enabled":
                    enabled_disabled(domain_obj.sms_mobile_worker_registration_enabled),
            }
            form = SettingsForm(initial=initial, cchq_domain=self.domain,
                cchq_is_previewer=self.previewer)
        return form

    @property
    def page_context(self):
        return {
            "form": self.form,
        }

    def post(self, request, *args, **kwargs):
        form = self.form
        if form.is_valid():
            domain_obj = Domain.get_by_name(self.domain, strict=True)
            field_map = [
                ("use_default_sms_response",
                 "use_default_sms_response"),
                ("default_sms_response",
                 "default_sms_response"),
                ("custom_case_username",
                 "custom_case_username"),
                ("send_to_duplicated_case_numbers",
                 "send_to_duplicated_case_numbers"),
                ("sms_conversation_length",
                 "sms_conversation_length"),
                ("count_messages_as_read_by_anyone",
                 "count_messages_as_read_by_anyone"),
                ("chat_message_count_threshold",
                 "custom_message_count_threshold"),
                ("restricted_sms_times",
                 "restricted_sms_times_json"),
                ("sms_conversation_times",
                 "sms_conversation_times_json"),
                ("sms_mobile_worker_registration_enabled",
                 "sms_mobile_worker_registration_enabled"),
            ]
            if self.previewer:
                field_map.append(
                    ("custom_chat_template",
                     "custom_chat_template")
                )
            for (model_field_name, form_field_name) in field_map:
                setattr(domain_obj, model_field_name,
                    form.cleaned_data[form_field_name])

            survey_traffic_option = form.cleaned_data["survey_traffic_option"]
            if survey_traffic_option == HIDE_ALL:
                domain_obj.filter_surveys_from_chat = True
                domain_obj.show_invalid_survey_responses_in_chat = False
            elif survey_traffic_option == SHOW_INVALID:
                domain_obj.filter_surveys_from_chat = True
                domain_obj.show_invalid_survey_responses_in_chat = True
            else:
                domain_obj.filter_surveys_from_chat = False
                domain_obj.show_invalid_survey_responses_in_chat = False

            if form.cleaned_data["sms_case_registration_enabled"]:
                domain_obj.sms_case_registration_enabled = True
                domain_obj.sms_case_registration_type = form.cleaned_data[
                    "sms_case_registration_type"]
                domain_obj.sms_case_registration_owner_id = form.cleaned_data[
                    "sms_case_registration_owner_id"]
                domain_obj.sms_case_registration_user_id = form.cleaned_data[
                    "sms_case_registration_user_id"]
            else:
                domain_obj.sms_case_registration_enabled = False

            domain_obj.save()
            messages.success(request, _("Changes Saved."))
        return self.get(request, *args, **kwargs)

    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(SMSSettingsView, self).dispatch(request, *args, **kwargs)
