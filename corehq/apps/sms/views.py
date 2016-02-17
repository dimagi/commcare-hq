#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8
from StringIO import StringIO
import base64
import logging
from datetime import datetime, timedelta, time
import re
import json
from couchdbkit import ResourceNotFound
import pytz
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, Http404
from django.shortcuts import render
from django.utils.decorators import method_decorator
from casexml.apps.case.models import CommCareCase
from corehq import privileges, toggles
from corehq.apps.hqadmin.views import BaseAdminSectionView
from corehq.apps.hqwebapp.doc_info import get_doc_info_by_id
from corehq.apps.hqwebapp.utils import get_bulk_upload_form, sign
from corehq.apps.reminders.util import can_use_survey_reminders
from corehq.apps.accounting.decorators import requires_privilege_with_fallback, requires_privilege_plaintext_response
from corehq.apps.api.models import require_api_user_permission, PERMISSION_POST_SMS, ApiUser
from corehq.apps.commtrack.models import AlertConfig
from corehq.apps.sms.api import (
    send_sms,
    incoming,
    send_sms_with_backend_name,
    send_sms_to_verified_number,
    DomainScopeValidationError,
    MessageMetadata,
)
from corehq.apps.domain.views import BaseDomainView, DomainViewMixin
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.sms.dbaccessors import get_forwarding_rules_for_domain
from corehq.apps.style.decorators import use_bootstrap3, use_timepicker, use_typeahead, use_select2, use_jquery_ui, \
    upgrade_knockout_js
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CouchUser, Permissions, CommCareUser
from corehq.apps.users import models as user_models
from corehq.apps.users.views.mobile.users import EditCommCareUserView
from corehq.apps.sms.models import (
    SMSLog, INCOMING, OUTGOING, ForwardingRule,
    LastReadMessage, MessagingEvent, SelfRegistrationInvitation,
    SQLMobileBackend, SQLMobileBackendMapping, PhoneLoadBalancingMixin
)
from corehq.apps.sms.mixin import VerifiedNumber, BadSMSConfigException
from corehq.apps.sms.forms import (ForwardingRuleForm, BackendMapForm,
                                   InitiateAddSMSBackendForm, SubscribeSMSForm,
                                   SettingsForm, SHOW_ALL, SHOW_INVALID, HIDE_ALL, ENABLED, DISABLED,
                                   DEFAULT, CUSTOM, SendRegistrationInviationsForm,
                                   WELCOME_RECIPIENT_NONE, WELCOME_RECIPIENT_CASE,
                                   WELCOME_RECIPIENT_MOBILE_WORKER, WELCOME_RECIPIENT_ALL, ComposeMessageForm)
from corehq.apps.sms.util import get_contact, get_sms_backend_classes
from corehq.apps.sms.messages import _MESSAGES
from corehq.apps.smsbillables.utils import country_name_from_isd_code_or_empty as country_name_from_code
from corehq.apps.groups.models import Group
from corehq.apps.domain.decorators import (
    login_and_domain_required,
    login_or_digest_ex,
    domain_admin_required,
    require_superuser,
)
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.util.dates import iso_string_to_datetime
from corehq.util.spreadsheets.excel import WorkbookJSONReader
from corehq.util.timezones.conversions import ServerTime, UserTime
from django.contrib import messages
from corehq.util.timezones.utils import get_timezone_for_user
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from corehq.apps.domain.models import Domain
from corehq.const import SERVER_DATETIME_FORMAT, SERVER_DATE_FORMAT
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
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
    return HttpResponseRedirect(reverse(ComposeMessageView.urlname, args=[domain]))


class BaseMessagingSectionView(BaseDomainView):
    section_name = ugettext_noop("Messaging")

    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, *args, **kwargs):
        return super(BaseMessagingSectionView, self).dispatch(*args, **kwargs)

    @property
    def section_url(self):
        return reverse("sms_default", args=[self.domain])


class BaseAdvancedMessagingSectionView(BaseMessagingSectionView):
    """
    Just like BaseMessagingSectionView, only requires access to inbound SMS
    as well.
    """
    @method_decorator(requires_privilege_with_fallback(privileges.INBOUND_SMS))
    def dispatch(self, *args, **kwargs):
        return super(BaseAdvancedMessagingSectionView, self).dispatch(*args, **kwargs)


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


class ComposeMessageView(BaseMessagingSectionView):
    template_name = 'sms/compose.html'
    urlname = 'sms_compose_message'
    page_title = _('Compose SMS Message')

    @property
    def page_context(self):
        page_context = super(ComposeMessageView, self).page_context
        tz = get_timezone_for_user(self.request.couch_user, self.domain)
        page_context.update({
            'now': datetime.utcnow(),
            'timezone': tz,
            'timezone_now': datetime.now(tz=tz),
            'form': ComposeMessageForm(domain=self.domain)
        })
        page_context.update(get_sms_autocomplete_context(self.request, self.domain))
        return page_context

    @method_decorator(require_permission(Permissions.edit_data))
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @use_bootstrap3
    @use_typeahead
    def dispatch(self, *args, **kwargs):
        return super(BaseMessagingSectionView, self).dispatch(*args, **kwargs)


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
    groups = Group.by_domain(domain)

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

        login_ids = {
            r['key']: r['id'] for r in CommCareUser.get_db().view(
                "users/by_username", keys=usernames, reduce=False).all()}
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
        reverse(ComposeMessageView.urlname, args=[domain])
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
        vn_id - the _id of a VerifiedNumber to send to (overrides contact_id)
        text - the text of the message
        backend_id - the name of the MobileBackend to use while sending
    """
    if request.method == "POST":
        phone_number = request.POST.get("phone_number", None)
        contact_id = request.POST.get("contact_id", None)
        vn_id = request.POST.get("vn_id", None)
        text = request.POST.get("text", None)
        backend_id = request.POST.get("backend_id", None)
        chat = request.POST.get("chat", None)
        contact = None

        if (phone_number is None and contact_id is None and not vn_id) or (text is None):
            return HttpResponseBadRequest("Not enough arguments.")

        vn = None
        if vn_id:
            try:
                vn = VerifiedNumber.get(vn_id)
            except ResourceNotFound:
                return HttpResponseBadRequest("VerifiedNumber not found.")

            if vn.domain != domain:
                return HttpResponseBadRequest("VerifiedNumber not found.")

            phone_number = vn.phone_number
            contact = vn.owner
        elif contact_id is not None:
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


class GlobalBackendMap(BaseAdminSectionView):
    urlname = 'global_backend_map'
    template_name = 'sms/backend_map.html'
    page_title = ugettext_lazy("Default Gateways")

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    @memoized
    def backends(self):
        return SQLMobileBackend.get_global_backends(SQLMobileBackend.SMS)

    @property
    @memoized
    def backend_map_form(self):
        if self.request.method == 'POST':
            return BackendMapForm(self.request.POST, backends=self.backends)

        backend_map = SQLMobileBackendMapping.get_prefix_to_backend_map(SQLMobileBackend.SMS)
        initial = {
            'catchall_backend_id': backend_map.catchall_backend_id,
            'backend_map': json.dumps([
                {'prefix': prefix, 'backend_id': backend_id}
                for prefix, backend_id in backend_map.backend_map_tuples
            ]),
        }
        return BackendMapForm(initial=initial, backends=self.backends)

    @use_bootstrap3
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(GlobalBackendMap, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'form': self.backend_map_form,
            'backends': self.backends,
        }

    def post(self, request, *args, **kwargs):
        form = self.backend_map_form
        if form.is_valid():
            new_backend_map = form.cleaned_data.get('backend_map')
            new_catchall_backend_id = form.cleaned_data.get('catchall_backend_id')

            with transaction.atomic():
                SQLMobileBackendMapping.get_prefix_to_backend_map.clear(
                    SQLMobileBackendMapping, SQLMobileBackend.SMS
                )
                SQLMobileBackendMapping.objects.filter(
                    is_global=True,
                    backend_type=SQLMobileBackend.SMS,
                ).delete()

                for prefix, backend_id in new_backend_map.items():
                    SQLMobileBackendMapping.objects.create(
                        is_global=True,
                        backend_type=SQLMobileBackend.SMS,
                        prefix=prefix,
                        backend_id=backend_id
                    )

                if new_catchall_backend_id:
                    SQLMobileBackendMapping.objects.create(
                        is_global=True,
                        backend_type=SQLMobileBackend.SMS,
                        prefix='*',
                        backend_id=new_catchall_backend_id
                    )

            messages.success(request, _("Changes Saved."))
            return HttpResponseRedirect(reverse(self.urlname))
        return self.get(request, *args, **kwargs)


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
                doc['_id'],
            ])
        elif doc['owner_doc_type'] == 'CommCareUser':
            mobile_worker_ids.append(owner_id)
            data.append([
                None,
                'mobile_worker',
                doc['phone_number'],
                owner_id,
                doc['_id'],
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
        vn_id = row[4]
        if row[1] == 'case':
            row[1] = _('Case')
            row[4] = reverse('case_details', args=[domain, contact_id])
        elif row[1] == 'mobile_worker':
            row[1] = _('Mobile Worker')
            row[4] = reverse(EditCommCareUserView.urlname, args=[domain, contact_id])
        else:
            row[4] = '#'
        row.append(reverse('sms_chat', args=[domain, contact_id, vn_id]))


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
def chat(request, domain, contact_id, vn_id=None):
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
        "vn_id": vn_id,
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

    @use_bootstrap3
    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(DomainSmsGatewayListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        return SQLMobileBackend.get_domain_backends(SQLMobileBackend.SMS, self.domain, count_only=True)

    @property
    def column_names(self):
        return [
            _("Gateway"),
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
        backends = SQLMobileBackend.get_domain_backends(
            SQLMobileBackend.SMS,
            self.domain,
            offset=self.skip,
            limit=self.limit
        )
        default_backend = SQLMobileBackend.get_domain_default_backend(
            SQLMobileBackend.SMS,
            self.domain
        )

        if len(backends) > 0 and not default_backend:
            yield {
                'itemData': {
                    'id': 'nodefault',
                    'name': "Automatic Choose",
                    'status': 'DEFAULT',
                },
                'template': 'gateway-automatic-template',
            }
        elif default_backend:
            yield {
                'itemData': self._fmt_backend_data(default_backend),
                'template': 'gateway-default-template',
            }

        default_backend_id = default_backend.pk if default_backend else None
        for backend in backends:
            if backend.pk != default_backend_id:
                yield {
                    'itemData': self._fmt_backend_data(backend),
                    'template': 'gateway-template',
                }

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
            'id': backend.pk,
            'name': backend.name,
            'description': backend.description,
            'supported_countries': supported_country_names,
            'editUrl': reverse(
                EditDomainGatewayView.urlname,
                args=[self.domain, backend.hq_api_id, backend.pk]
            ) if is_editable else "",
            'canDelete': is_editable,
            'isGlobal': backend.is_global,
            'isShared': not backend.is_global and backend.domain != self.domain,
            'deleteModalId': 'delete_%s' % backend.pk,
        }

    def _get_backend_from_item_id(self, item_id):
        try:
            item_id = int(item_id)
            backend = SQLMobileBackend.load(item_id)
            return item_id, backend
        except (BadSMSConfigException, SQLMobileBackend.DoesNotExist, TypeError, ValueError):
            raise Http404()

    def get_deleted_item_data(self, item_id):
        item_id, backend = self._get_backend_from_item_id(item_id)

        if backend.is_global or backend.domain != self.domain:
            raise Http404()

        # Do not actually delete so that linkage always exists between SMS and
        # MobileBackend for billable history
        backend.soft_delete()

        return {
            'itemData': self._fmt_backend_data(backend),
            'template': 'gateway-deleted-template',
        }

    def refresh_item(self, item_id):
        item_id, backend = self._get_backend_from_item_id(item_id)

        if not backend.domain_is_authorized(self.domain):
            raise Http404()

        domain_default_backend_id = SQLMobileBackend.get_domain_default_backend(
            SQLMobileBackend.SMS,
            self.domain,
            id_only=True
        )

        if domain_default_backend_id == item_id:
            SQLMobileBackendMapping.unset_default_domain_backend(self.domain)
        else:
            SQLMobileBackendMapping.set_default_domain_backend(self.domain, backend)

    @property
    def allowed_actions(self):
        actions = super(DomainSmsGatewayListView, self).allowed_actions
        return actions + ['new_backend']

    def post(self, request, *args, **kwargs):
        if self.action == 'new_backend':
            hq_api_id = request.POST['hq_api_id']
            if (
                toggles.TELERIVET_SETUP_WALKTHROUGH.enabled(self.domain) and
                hq_api_id == SQLTelerivetBackend.get_api_id()
            ):
                from corehq.messaging.smsbackends.telerivet.views import TelerivetSetupView
                return HttpResponseRedirect(reverse(TelerivetSetupView.urlname, args=[self.domain]))
            return HttpResponseRedirect(reverse(AddDomainGatewayView.urlname, args=[self.domain, hq_api_id]))
        return self.paginate_crud_response


class AddGatewayViewMixin(object):
    """
    A mixin to help extract the common functionality between adding/editing
    domain-level backends and adding/editing global backends.
    """

    @property
    def is_superuser(self):
        return self.request.couch_user.is_superuser

    @property
    @memoized
    def hq_api_id(self):
        return self.kwargs.get('hq_api_id')

    @property
    @memoized
    def backend_class(self):
        # Superusers can create/edit any backend
        # Regular users can only create/edit Telerivet backends for now
        if not self.is_superuser and self.hq_api_id != SQLTelerivetBackend.get_api_id():
            raise Http404()
        backend_classes = get_sms_backend_classes()
        try:
            return backend_classes[self.hq_api_id]
        except KeyError:
            raise Http404()

    @property
    def use_load_balancing(self):
        return issubclass(self.backend_class, PhoneLoadBalancingMixin)

    @property
    def page_name(self):
        return _("Add %s Gateway") % self.backend_class.get_generic_name()

    @property
    def button_text(self):
        return _("Create %s Gateway") % self.backend_class.get_generic_name()

    @property
    def page_context(self):
        return {
            'form': self.backend_form,
            'button_text': self.button_text,
            'use_load_balancing': self.use_load_balancing,
        }

    def post(self, request, *args, **kwargs):
        if self.backend_form.is_valid():
            self.backend.name = self.backend_form.cleaned_data.get('name')
            self.backend.description = self.backend_form.cleaned_data.get('description')
            self.backend.reply_to_phone_number = self.backend_form.cleaned_data.get('reply_to_phone_number')

            extra_fields = {}
            for key, value in self.backend_form.cleaned_data.items():
                if key in self.backend.get_available_extra_fields():
                    extra_fields[key] = value
            self.backend.set_extra_fields(**extra_fields)

            if self.use_load_balancing:
                self.backend.load_balancing_numbers = self.backend_form.cleaned_data['phone_numbers']

            self.backend.save()
            if not self.backend.is_global:
                self.backend.set_shared_domains(self.backend_form.cleaned_data.get('authorized_domains'))
            return self.redirect_to_gateway_list()
        return self.get(request, *args, **kwargs)

    @property
    def backend(self):
        raise NotImplementedError()

    @property
    def page_url(self):
        raise NotImplementedError()

    @property
    def backend_form(self):
        raise NotImplementedError()

    @property
    def parent_pages(self):
        raise NotImplementedError()

    def redirect_to_gateway_list(self):
        raise NotImplementedError()


class AddDomainGatewayView(AddGatewayViewMixin, BaseMessagingSectionView):
    urlname = 'add_domain_gateway'
    template_name = 'sms/add_gateway.html'
    page_title = ugettext_lazy("Add SMS Gateway")

    @property
    @memoized
    def backend(self):
        return self.backend_class(
            domain=self.domain,
            is_global=False,
            backend_type=SQLMobileBackend.SMS,
            hq_api_id=self.backend_class.get_api_id()
        )

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.hq_api_id])

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        if self.request.method == 'POST':
            return form_class(
                self.request.POST,
                button_text=self.button_text,
                domain=self.domain,
                backend_id=None
            )
        return form_class(
            button_text=self.button_text,
            domain=self.domain,
            backend_id=None
        )

    @property
    def parent_pages(self):
        return [{
            'title': DomainSmsGatewayListView.page_title,
            'url': reverse(DomainSmsGatewayListView.urlname, args=[self.domain]),
        }]

    def redirect_to_gateway_list(self):
        return HttpResponseRedirect(reverse(DomainSmsGatewayListView.urlname, args=[self.domain]))

    @use_bootstrap3
    @use_select2
    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(AddDomainGatewayView, self).dispatch(request, *args, **kwargs)


class EditDomainGatewayView(AddDomainGatewayView):
    urlname = 'edit_domain_gateway'
    page_title = ugettext_lazy("Edit SMS Gateway")

    @property
    def backend_id(self):
        return self.kwargs['backend_id']

    @property
    @memoized
    def backend(self):
        try:
            backend = self.backend_class.objects.get(pk=self.backend_id)
        except ResourceNotFound:
            raise Http404()
        if (
            backend.is_global or
            backend.domain != self.domain or
            backend.hq_api_id != self.backend_class.get_api_id() or
            backend.deleted
        ):
            raise Http404()
        return backend

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        authorized_domains = self.backend.get_authorized_domain_list()
        initial = {
            'name': self.backend.name,
            'description': self.backend.description,
            'give_other_domains_access': len(authorized_domains) > 0,
            'authorized_domains': ','.join(authorized_domains),
            'reply_to_phone_number': self.backend.reply_to_phone_number,
        }
        initial.update(self.backend.get_extra_fields())

        if self.use_load_balancing:
            initial['phone_numbers'] = json.dumps(
                [{'phone_number': p} for p in self.backend.load_balancing_numbers]
            )

        if self.request.method == 'POST':
            return form_class(
                self.request.POST,
                initial=initial,
                button_text=self.button_text,
                domain=self.domain,
                backend_id=self.backend.pk
            )
        return form_class(
            initial=initial,
            button_text=self.button_text,
            domain=self.domain,
            backend_id=self.backend.pk
        )

    @property
    def page_name(self):
        return _("Edit %s Gateway") % self.backend_class.get_generic_name()

    @property
    def button_text(self):
        return _("Update %s Gateway") % self.backend_class.get_generic_name()

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs=self.kwargs)


class GlobalSmsGatewayListView(CRUDPaginatedViewMixin, BaseAdminSectionView):
    template_name = "sms/global_gateway_list.html"
    urlname = 'list_global_backends'
    page_title = ugettext_noop("SMS Connectivity")

    @use_bootstrap3
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(GlobalSmsGatewayListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    @memoized
    def total(self):
        return SQLMobileBackend.get_global_backends(SQLMobileBackend.SMS, count_only=True)

    @property
    def column_names(self):
        return [
            _("Gateway"),
            _("Description"),
            _("Supported Countries"),
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
        backends = SQLMobileBackend.get_global_backends(
            SQLMobileBackend.SMS,
            offset=self.skip,
            limit=self.limit
        )

        for backend in backends:
            yield {
                'itemData': self._fmt_backend_data(backend),
                'template': 'gateway-template',
            }

    def _fmt_backend_data(self, backend):
        if len(backend.supported_countries) > 0:
            if backend.supported_countries[0] == '*':
                supported_country_names = _('Multiple%s') % '*'
            else:
                supported_country_names = ', '.join(
                    [_(country_name_from_code(int(c))) for c in backend.supported_countries])
        else:
            supported_country_names = ''
        return {
            'id': backend.pk,
            'name': backend.name,
            'description': backend.description,
            'supported_countries': supported_country_names,
            'editUrl': reverse(
                EditGlobalGatewayView.urlname,
                args=[backend.hq_api_id, backend.pk]
            ),
            'deleteModalId': 'delete_%s' % backend.pk,
        }

    def _get_backend_from_item_id(self, item_id):
        try:
            item_id = int(item_id)
            backend = SQLMobileBackend.load(item_id)
            return item_id, backend
        except (BadSMSConfigException, SQLMobileBackend.DoesNotExist, TypeError, ValueError):
            raise Http404()

    def get_deleted_item_data(self, item_id):
        item_id, backend = self._get_backend_from_item_id(item_id)

        if not backend.is_global:
            raise Http404()

        # Do not actually delete so that linkage always exists between SMS and
        # MobileBackend for billable history
        backend.soft_delete()

        return {
            'itemData': self._fmt_backend_data(backend),
            'template': 'gateway-deleted-template',
        }

    @property
    def allowed_actions(self):
        actions = super(GlobalSmsGatewayListView, self).allowed_actions
        return actions + ['new_backend']

    def post(self, request, *args, **kwargs):
        if self.action == 'new_backend':
            hq_api_id = request.POST['hq_api_id']
            return HttpResponseRedirect(reverse(AddGlobalGatewayView.urlname, args=[hq_api_id]))
        return self.paginate_crud_response


class AddGlobalGatewayView(AddGatewayViewMixin, BaseAdminSectionView):
    urlname = 'add_global_gateway'
    template_name = 'sms/add_gateway.html'
    page_title = ugettext_lazy("Add SMS Gateway")

    @property
    @memoized
    def backend(self):
        return self.backend_class(
            is_global=True,
            backend_type=SQLMobileBackend.SMS,
            hq_api_id=self.backend_class.get_api_id()
        )

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.hq_api_id])

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        if self.request.method == 'POST':
            return form_class(
                self.request.POST,
                button_text=self.button_text,
                domain=None,
                backend_id=None
            )
        return form_class(
            button_text=self.button_text,
            domain=None,
            backend_id=None
        )

    @property
    def parent_pages(self):
        return [{
            'title': GlobalSmsGatewayListView.page_title,
            'url': reverse(GlobalSmsGatewayListView.urlname),
        }]

    def redirect_to_gateway_list(self):
        return HttpResponseRedirect(reverse(GlobalSmsGatewayListView.urlname))

    @use_bootstrap3
    @use_select2
    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        return super(AddGlobalGatewayView, self).dispatch(request, *args, **kwargs)


class EditGlobalGatewayView(AddGlobalGatewayView):
    urlname = 'edit_global_gateway'
    page_title = ugettext_lazy("Edit SMS Gateway")

    @property
    def backend_id(self):
        return self.kwargs['backend_id']

    @property
    @memoized
    def backend(self):
        try:
            backend = self.backend_class.objects.get(pk=self.backend_id)
        except ResourceNotFound:
            raise Http404()
        if (
            not backend.is_global or
            backend.deleted or
            backend.hq_api_id != self.backend_class.get_api_id()
        ):
            raise Http404()
        return backend

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        initial = {
            'name': self.backend.name,
            'description': self.backend.description,
            'reply_to_phone_number': self.backend.reply_to_phone_number,
        }
        initial.update(self.backend.get_extra_fields())

        if self.use_load_balancing:
            initial['phone_numbers'] = json.dumps(
                [{'phone_number': p} for p in self.backend.load_balancing_numbers]
            )

        if self.request.method == 'POST':
            return form_class(
                self.request.POST,
                initial=initial,
                button_text=self.button_text,
                domain=None,
                backend_id=self.backend.pk
            )
        return form_class(
            initial=initial,
            button_text=self.button_text,
            domain=None,
            backend_id=self.backend.pk
        )

    @property
    def page_name(self):
        return _("Edit %s Gateway") % self.backend_class.get_generic_name()

    @property
    def button_text(self):
        return _("Update %s Gateway") % self.backend_class.get_generic_name()

    @property
    def page_url(self):
        return reverse(self.urlname, kwargs=self.kwargs)


class SubscribeSMSView(BaseMessagingSectionView):
    template_name = "sms/subscribe_sms.html"
    urlname = 'subscribe_sms'
    page_title = ugettext_noop("Subscribe SMS")

    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @use_bootstrap3
    def dispatch(self, *args, **kwargs):
        return super(SubscribeSMSView, self).dispatch(*args, **kwargs)

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


class SMSLanguagesView(BaseMessagingSectionView):
    urlname = 'sms_languages'
    template_name = "sms/languages.html"
    page_title = ugettext_noop("Languages")

    @use_bootstrap3
    @use_jquery_ui
    # @upgrade_knockout_js
    @method_decorator(domain_admin_required)
    def dispatch(self, *args, **kwargs):
        return super(SMSLanguagesView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        with StandaloneTranslationDoc.get_locked_obj(self.domain, "sms", create=True) as tdoc:
            if len(tdoc.langs) == 0:
                tdoc.langs = ["en"]
                tdoc.translations["en"] = {}
                tdoc.save()
        context = {
            "domain": self.domain,
            "sms_langs": tdoc.langs,
            "bulk_upload": {
                "action": reverse("upload_sms_translations", args=(self.domain,)),
                "download_url": reverse("download_sms_translations", args=(self.domain,)),
                "adjective": _("messaging translation"),
                "plural_noun": _("messaging translations"),
            },
        }
        context.update({
            "bulk_upload_form": get_bulk_upload_form(context),
        })

        return context


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def edit_sms_languages(request, domain):
    """
    Accepts same post body as corehq.apps.app_manager.views.edit_app_langs
    """
    with StandaloneTranslationDoc.get_locked_obj(domain, "sms",
        create=True) as tdoc:
        try:
            from corehq.apps.app_manager.views.utils import validate_langs
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

    def get_welcome_message_recipient(self, domain_obj):
        if (
            domain_obj.enable_registration_welcome_sms_for_case and
            domain_obj.enable_registration_welcome_sms_for_mobile_worker
        ):
            return WELCOME_RECIPIENT_ALL
        elif domain_obj.enable_registration_welcome_sms_for_case:
            return WELCOME_RECIPIENT_CASE
        elif domain_obj.enable_registration_welcome_sms_for_mobile_worker:
            return WELCOME_RECIPIENT_MOBILE_WORKER
        else:
            return WELCOME_RECIPIENT_NONE

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
                "registration_welcome_message":
                    self.get_welcome_message_recipient(domain_obj),
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

            domain_obj.enable_registration_welcome_sms_for_case = \
                form.enable_registration_welcome_sms_for_case

            domain_obj.enable_registration_welcome_sms_for_mobile_worker = \
                form.enable_registration_welcome_sms_for_mobile_worker

            domain_obj.save()
            messages.success(request, _("Changes Saved."))
        return self.get(request, *args, **kwargs)

    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @use_bootstrap3
    @use_timepicker
    def dispatch(self, request, *args, **kwargs):
        return super(SMSSettingsView, self).dispatch(request, *args, **kwargs)


class ManageRegistrationInvitationsView(BaseAdvancedMessagingSectionView, CRUDPaginatedViewMixin):
    template_name = 'sms/manage_registration_invitations.html'
    urlname = 'sms_manage_registration_invitations'
    page_title = ugettext_lazy('Manage Registration Invitations')

    limit_text = ugettext_noop("invitations per page")
    empty_notification = ugettext_noop("No registration invitations sent yet.")
    loading_message = ugettext_noop("Loading invitations...")
    strict_domain_fetching = True

    @property
    @memoized
    def invitations_form(self):
        if self.request.method == 'POST':
            return SendRegistrationInviationsForm(self.request.POST, domain=self.domain)
        else:
            return SendRegistrationInviationsForm(domain=self.domain)

    @property
    @memoized
    def project_timezone(self):
        return get_timezone_for_user(None, self.domain)

    @property
    def parameters(self):
        return self.request.POST if self.request.method == 'POST' else self.request.GET

    @property
    def page_context(self):
        context = self.pagination_context
        context.update({
            'form': self.invitations_form,
            'sms_mobile_worker_registration_enabled':
                self.domain_object.sms_mobile_worker_registration_enabled,
        })
        return context

    @property
    def total(self):
        return SelfRegistrationInvitation.objects.filter(domain=self.domain).count()

    @property
    def column_names(self):
        return [
            _('Created On'),
            _('Phone Number'),
            _('Status'),
            _('Expiration Date'),
            _('Application'),
            _('Phone Type'),
        ]

    def format_status(self, invitation):
        if invitation.status == SelfRegistrationInvitation.STATUS_REGISTERED:
            registered_date = (ServerTime(invitation.registered_date)
                               .user_time(self.project_timezone)
                               .done()
                               .strftime(SERVER_DATETIME_FORMAT))
            return _("Registered on %(date)s") % {'date': registered_date}
        else:
            return {
                SelfRegistrationInvitation.STATUS_PENDING: _("Pending"),
                SelfRegistrationInvitation.STATUS_EXPIRED: _("Expired"),
            }.get(invitation.status)

    @property
    def paginated_list(self):
        invitations = SelfRegistrationInvitation.objects.filter(
            domain=self.domain
        ).order_by('-created_date')
        doc_info_cache = {}
        for invitation in invitations[self.skip:self.skip + self.limit]:
            if invitation.app_id in doc_info_cache:
                doc_info = doc_info_cache[invitation.app_id]
            else:
                doc_info = get_doc_info_by_id(self.domain, invitation.app_id)
                doc_info_cache[invitation.app_id] = doc_info
            yield {
                'itemData': {
                    'id': invitation.pk,
                    'created_date': (ServerTime(invitation.created_date)
                                     .user_time(self.project_timezone)
                                     .done()
                                     .strftime(SERVER_DATETIME_FORMAT)),
                    'phone_number': '+%s' % invitation.phone_number,
                    'status': self.format_status(invitation),
                    'expiration_date': invitation.expiration_date.strftime(SERVER_DATE_FORMAT),
                    'app_name': doc_info.display,
                    'app_link': doc_info.link,
                    'phone_type': dict(SelfRegistrationInvitation.PHONE_TYPE_CHOICES).get(invitation.phone_type),
                },
                'template': 'invitations-template',
            }

    def post(self, *args, **kwargs):
        if self.request.POST.get('action') == 'invite':
            if not self.domain_object.sms_mobile_worker_registration_enabled:
                return self.get(*args, **kwargs)
            if self.invitations_form.is_valid():
                phone_numbers = self.invitations_form.cleaned_data.get('phone_numbers')
                app_id = self.invitations_form.cleaned_data.get('app_id')
                result = SelfRegistrationInvitation.initiate_workflow(
                    self.domain,
                    phone_numbers,
                    app_id=app_id
                )
                success_numbers, invalid_format_numbers, numbers_in_use = result
                if success_numbers:
                    messages.success(
                        self.request,
                        _("Invitations sent to: %(phone_numbers)s") % {
                            'phone_numbers': ','.join(success_numbers),
                        }
                    )
                if invalid_format_numbers:
                    messages.error(
                        self.request,
                        _("Invitations could not be sent to: %(phone_numbers)s. "
                          "These number(s) are in an invalid format.") % {
                            'phone_numbers': ','.join(invalid_format_numbers)
                        }
                    )
                if numbers_in_use:
                    messages.error(
                        self.request,
                        _("Invitations could not be sent to: %(phone_numbers)s. "
                          "These number(s) are already in use.") % {
                            'phone_numbers': ','.join(numbers_in_use)
                        }
                    )
            return self.get(*args, **kwargs)
        else:
            if not self.domain_object.sms_mobile_worker_registration_enabled:
                raise Http404()
            return self.paginate_crud_response


class InvitationAppInfoView(View, DomainViewMixin):
    urlname = 'sms_registration_invitation_app_info'

    @property
    @memoized
    def token(self):
        token = self.kwargs.get('token')
        if not token:
            raise Http404()
        return token

    @property
    @memoized
    def invitation(self):
        invitation = SelfRegistrationInvitation.by_token(self.token)
        if not invitation:
            raise Http404()
        return invitation

    def get(self, *args, **kwargs):
        if not self.invitation.odk_url:
            raise Http404()
        url = str(self.invitation.odk_url).strip()
        response = 'ccapp: %s signature: %s' % (url, sign(url))
        response = base64.b64encode(response)
        return HttpResponse(response)

    def post(self, *args, **kwargs):
        return self.get(*args, **kwargs)


class IncomingBackendView(View):
    def dispatch(self, request, api_key, *args, **kwargs):
        try:
            api_user = ApiUser.get('ApiUser-%s' % api_key)
        except ResourceNotFound:
            return HttpResponse(status=401)

        if api_user.doc_type != 'ApiUser' or not api_user.has_permission(PERMISSION_POST_SMS):
            return HttpResponse(status=401)

        return super(IncomingBackendView, self).dispatch(request, api_key, *args, **kwargs)


class NewIncomingBackendView(View):
    domain = None
    backend_couch_id = None

    @property
    def backend_class(self):
        """
        Should return the model class of the backend (a subclass of SQLMobileBackend).
        """
        raise NotImplementedError("Please implement this method")

    @method_decorator(csrf_exempt)
    def dispatch(self, request, api_key, *args, **kwargs):
        try:
            self.domain, self.backend_couch_id = SQLMobileBackend.get_backend_info_by_api_key(
                self.backend_class.get_api_id(),
                api_key
            )
        except SQLMobileBackend.DoesNotExist:
            return HttpResponse(status=401)

        return super(NewIncomingBackendView, self).dispatch(request, api_key, *args, **kwargs)
