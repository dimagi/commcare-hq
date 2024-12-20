#!/usr/bin/env python
import io
import json
import re
import uuid
from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from couchdbkit import ResourceNotFound
from django_prbac.utils import has_privilege
from memoized import memoized
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher

from couchexport.export import export_raw
from couchexport.models import Format
from couchexport.shortcuts import export_response
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.view import get_file
from dimagi.utils.logging import notify_exception
from dimagi.utils.parsing import json_format_datetime, string_to_boolean
from dimagi.utils.web import json_response

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import (
    requires_privilege_plaintext_response,
    requires_privilege_with_fallback,
)
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.commtrack.models import AlertConfig
from corehq.apps.domain.decorators import (
    domain_admin_required,
    login_and_domain_required,
    login_or_digest_ex,
    require_superuser,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.base import BaseDomainView, DomainViewMixin
from corehq.apps.groups.models import Group
from corehq.apps.hqadmin.views.users import BaseAdminSectionView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.hqwebapp.decorators import (
    use_datatables,
    use_jquery_ui,
    use_timepicker,
)
from corehq.apps.hqwebapp.utils import get_bulk_upload_form
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.reminders.util import get_two_way_number_for_recipient
from corehq.apps.sms.api import (
    MessageMetadata,
    get_inbound_phone_entry,
    incoming,
    send_sms,
    send_sms_to_verified_number,
    send_sms_with_backend_name,
)
from corehq.apps.sms.forms import (
    CUSTOM,
    DEFAULT,
    DISABLED,
    ENABLED,
    HIDE_ALL,
    LANGUAGE_FALLBACK_UNTRANSLATED,
    SHOW_ALL,
    SHOW_INVALID,
    WELCOME_RECIPIENT_ALL,
    WELCOME_RECIPIENT_CASE,
    WELCOME_RECIPIENT_MOBILE_WORKER,
    WELCOME_RECIPIENT_NONE,
    BackendMapForm,
    ComposeMessageForm,
    InitiateAddSMSBackendForm,
    SentTestSmsForm,
    SettingsForm,
    SubscribeSMSForm,
)
from corehq.apps.sms.messages import _MESSAGES
from corehq.apps.sms.mixin import BadSMSConfigException
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
    SMS,
    MessagingEvent,
    PhoneLoadBalancingMixin,
    PhoneNumber,
    SQLLastReadMessage,
    SQLMobileBackend,
    SQLMobileBackendMapping,
)
from corehq.apps.sms.phonenumbers_helper import country_name_for_country_code
from corehq.apps.sms.util import (
    ContactNotFoundException,
    get_contact,
    get_or_create_sms_translations,
    get_sms_backend_classes,
    is_superuser_or_contractor,
)
from corehq.apps.smsforms.models import (
    SQLXFormsSession,
    XFormsSessionSynchronization,
)
from corehq.apps.users import models as user_models
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import CommCareUser, CouchUser, HqPermissions
from corehq.apps.users.views.mobile.users import EditCommCareUserView
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling.async_handlers import SMSSettingsAsyncHandler
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.util.dates import iso_string_to_datetime
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime, UserTime
from corehq.util.timezones.utils import get_timezone_for_user
from corehq.util.workbook_json.excel import get_single_worksheet

# Tuple of (description, days in the past)
SMS_CHAT_HISTORY_CHOICES = (
    (gettext_noop("Yesterday"), 1),
    (gettext_noop("1 Week"), 7),
    (gettext_noop("30 Days"), 30),
)


@login_and_domain_required
def default(request, domain):
    from corehq.messaging.scheduling.views import MessagingDashboardView
    return HttpResponseRedirect(reverse(MessagingDashboardView.urlname, args=[domain]))


class BaseMessagingSectionView(BaseDomainView):
    section_name = gettext_noop("Messaging")

    @cached_property
    def can_use_inbound_sms(self):
        return has_privilege(self.request, privileges.INBOUND_SMS)

    @cached_property
    def is_system_admin(self):
        return is_superuser_or_contractor(self.request.couch_user)

    @cached_property
    def is_granted_messaging_access(self):
        if settings.ENTERPRISE_MODE or self.domain_object.granted_messaging_access:
            return True
        subscription = Subscription.get_active_subscription_by_domain(self.domain_object)
        if subscription is not None:
            return subscription.plan_version.plan.name == DefaultProductPlan.get_default_plan_version(
                edition=SoftwarePlanEdition.ENTERPRISE
            ).plan.name
        return False

    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    @method_decorator(require_permission(HqPermissions.edit_messaging))
    def dispatch(self, request, *args, **kwargs):
        if not self.is_granted_messaging_access:
            return render(request, "sms/wall.html", self.main_context)
        return super(BaseMessagingSectionView, self).dispatch(request, *args, **kwargs)

    @property
    def section_url(self):
        return reverse("sms_default", args=[self.domain])


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
        return page_context


def get_sms_autocomplete_context(domain):
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
    return contacts


@login_and_domain_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def send_to_recipients(request, domain):
    # This is invoked from both the ComposeMessageView as well as from
    # the view that sends SMS to users when publishing an app.
    # Currently the permission to publish an app is just the login_and_domain_required
    # decorator, and this view matches that.

    recipients = request.POST.getlist('recipients')
    message = request.POST.get('message')
    if not recipients:
        messages.error(request, _("You didn't specify any recipients"))
    elif not message:
        messages.error(request, _("You can't send an empty message"))
    else:
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
            elif re.match(r'^\+\d+$', recipient):  # here we expect it to have a plus sign
                def wrap_user_by_type(u):
                    return getattr(user_models, u['doc']['doc_type']).wrap(u['doc'])

                phone_users = CouchUser.view("users/by_default_phone",  # search both with and w/o the plus
                    keys=[recipient, recipient[1:]], include_docs=True,
                    wrapper=wrap_user_by_type).all()

                phone_users = [u for u in phone_users if u.is_member_of(domain)]
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
        login_ids = list(login_ids.values())

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

        if empty_groups or failed_numbers or unknown_usernames or no_numbers:
            if empty_groups:
                messages.error(request, _("The following groups don't exist: ") + (', '.join(empty_groups)))
            if no_numbers:
                messages.error(request,
                    _("The following users don't have phone numbers: ") + (', '.join(no_numbers)))
            if failed_numbers:
                messages.error(request,
                    _("Couldn't send to the following number(s): ") + (', '.join(failed_numbers)))
            if unknown_usernames:
                messages.error(request,
                    _("Couldn't find the following user(s): ") + (', '.join(unknown_usernames)))
            if sent:
                messages.success(request, _("Successfully sent: ") + (', '.join(sent)))
            else:
                messages.info(request, _("No messages were sent."))
        else:
            messages.success(request, _("Message sent"))

    return HttpResponseRedirect(
        request.META.get('HTTP_REFERER')
        or reverse(ComposeMessageView.urlname, args=[domain])
    )


class TestSMSMessageView(BaseDomainView):
    urlname = 'message_test'
    template_name = 'sms/message_tester.html'
    section_name = gettext_lazy("Messaging")
    page_title = gettext_lazy("Test SMS Message")

    @property
    def section_url(self):
        return reverse('sms_default', args=(self.domain,))

    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.INBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(TestSMSMessageView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        return {
            'form': self.get_form()
        }

    @memoized
    def get_form(self):
        backends = SQLMobileBackend.get_domain_backends(
            SQLMobileBackend.SMS,
            self.domain,
        )
        if self.request.method == 'POST':
            return SentTestSmsForm(
                self.request.POST,
                domain=self.domain,
                backends=backends,
            )

        default_backend = SQLMobileBackend.get_domain_default_backend(
            SQLMobileBackend.SMS,
            self.domain
        )
        initial = None
        if default_backend:
            initial = {'backend_id': default_backend.couch_id}
        return SentTestSmsForm(
            initial=initial,
            domain=self.domain,
            backends=backends,
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            phone_number = form.cleaned_data.get("phone_number", "")
            message = form.cleaned_data.get("message", "")
            backend_id = form.cleaned_data.get("backend_id", "")
            claim_channel = form.cleaned_data.get("claim_channel", False)

            error_message = self._check_phone_number(phone_number, backend_id, claim_channel)
            if error_message:
                messages.error(request, error_message)
                return self.get(request, *args, **kwargs)

            backend = SQLMobileBackend.load(backend_id, is_couch_id=True)
            incoming(
                phone_number, message, backend.get_api_id(),
                domain_scope=self.domain, backend_id=backend.couch_id,
                backend_message_id="message_test"
            )
            messages.success(
                request,
                _("Test message received.")
            )

        return self.get(request, *args, **kwargs)

    def _check_phone_number(self, phone_number, backend_id, claim_channel):
        phone_entry, has_domain_two_way_scope = get_inbound_phone_entry(phone_number, backend_id)
        if not phone_entry or phone_entry.domain != self.domain:
            msg = _("Invalid phone number. Please choose a "
                    "two-way phone number belonging to a contact in your project.")
            if not toggles.ONE_PHONE_NUMBER_MULTIPLE_CONTACTS.enabled(self.domain):
                return msg

            phone_entry_this_domain = PhoneNumber.get_two_way_number_with_domain_scope(
                phone_number, [self.domain])
            if claim_channel and phone_entry_this_domain:
                # attempt to claim the channel
                fake_session = SQLXFormsSession(
                    session_id=uuid.uuid4().hex,
                    connection_id=phone_entry_this_domain.owner_id,
                    phone_number=phone_entry_this_domain.phone_number
                )
                if XFormsSessionSynchronization.set_channel_for_affinity(fake_session):
                    # re-check but don't attempt a claim this time
                    return self._check_phone_number(phone_number, backend_id, claim_channel=False)

            return _("Invalid phone number. Either this number is not assigned to a contact in your "
                     "project or there is an active session for this number in another project space. "
                     "To 'claim' this channel use the 'claim this channel' checkbox or start a new SMS "
                     "survey with this number and wait for the first message to be sent.")


@csrf_exempt
@require_permission(HqPermissions.edit_messaging, login_decorator=login_or_digest_ex(allow_cc_users=True))
@requires_privilege_plaintext_response(privileges.OUTBOUND_SMS)
def api_send_sms(request, domain):
    """
    An API to send SMS.
    Expected post parameters:
        phone_number - the phone number to send to
        contact_id - the _id of a contact to send to (overrides phone_number)
        vn_id - the couch_id of a PhoneNumber to send to (overrides contact_id)
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
            vn = PhoneNumber.by_couch_id(vn_id)
            if not vn:
                return HttpResponseBadRequest("PhoneNumber not found.")

            if vn.domain != domain:
                return HttpResponseBadRequest("PhoneNumber not found.")

            phone_number = vn.phone_number
            contact = vn.owner
        elif contact_id is not None:
            try:
                contact = get_contact(domain, contact_id)
                assert contact is not None
                assert contact.domain == domain
            except Exception:
                return HttpResponseBadRequest("Contact not found.")

            vn = get_two_way_number_for_recipient(contact)
            if not vn:
                return HttpResponseBadRequest("Contact has no phone number.")
            phone_number = vn.phone_number

        try:
            chat_workflow = string_to_boolean(chat)
        except Exception:
            chat_workflow = False

        if chat_workflow:
            chat_user_id = request.couch_user.get_id
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


class GlobalBackendMap(BaseAdminSectionView):
    urlname = 'global_backend_map'
    template_name = 'sms/backend_map.html'
    page_title = gettext_lazy("Default Gateways")

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

            messages.success(request, _("Changes saved."))
            return HttpResponseRedirect(reverse(self.urlname))
        return self.get(request, *args, **kwargs)


class ChatOverSMSView(BaseMessagingSectionView):
    urlname = 'chat_contacts'
    template_name = 'sms/chat_contacts.html'
    page_title = _("Chat over SMS")

    @use_datatables
    def dispatch(self, *args, **kwargs):
        return super(ChatOverSMSView, self).dispatch(*args, **kwargs)


def get_case_contact_info(domain_obj, case_ids):
    data = {}
    for case in CommCareCase.objects.iter_cases(case_ids, domain_obj.name):
        if domain_obj.custom_case_username:
            name = case.get_case_property(domain_obj.custom_case_username)
        else:
            name = case.name
        data[case.case_id] = [name or _('(unknown)')]
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
    client = cache_core.get_redis_client()
    cached_data = client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)

    domain_obj = Domain.get_by_name(domain, strict=True)
    case_ids = []
    mobile_worker_ids = []
    data = []

    if toggles.INBOUND_SMS_LENIENCY.enabled(domain):
        phone_numbers_seen = set()
        phone_numbers = []
        for p in PhoneNumber.by_domain(domain).order_by('phone_number', '-is_two_way', 'created_on', 'couch_id'):
            if p.phone_number not in phone_numbers_seen:
                phone_numbers.append(p)
                phone_numbers_seen.add(p.phone_number)
    else:
        phone_numbers = PhoneNumber.by_domain(domain).filter(is_two_way=True)

    for p in phone_numbers:
        if p.owner_doc_type == 'CommCareCase':
            case_ids.append(p.owner_id)
            data.append([
                None,
                'case',
                p.phone_number,
                p.owner_id,
                p.couch_id,
            ])
        elif p.owner_doc_type == 'CommCareUser':
            mobile_worker_ids.append(p.owner_id)
            data.append([
                None,
                'mobile_worker',
                p.phone_number,
                p.owner_id,
                p.couch_id,
            ])
    contact_data = get_case_contact_info(domain_obj, case_ids)
    contact_data.update(get_mobile_worker_contact_info(domain_obj, mobile_worker_ids))
    for row in data:
        contact_info = contact_data.get(row[3])
        row[0] = contact_info[0] if contact_info else _('(unknown)')

    # Save the data to the cache for faster lookup next time.
    # If there isn't much data, don't bother with the cache, responsiveness is more important.
    if len(data) > 100:
        try:
            client.set(cache_key, json.dumps(data))
            client.expire(cache_key, cache_expiration)
        except Exception:
            pass

    return data


def format_contact_data(domain, data):
    for row in data:
        contact_id = row[3]
        vn_id = row[4]
        if row[1] == 'case':
            row[1] = _('Case')
            row[4] = reverse('case_data', args=[domain, contact_id])
        elif row[1] == 'mobile_worker':
            row[1] = _('Mobile Worker')
            row[4] = reverse(EditCommCareUserView.urlname, args=[domain, contact_id])
        else:
            row[4] = '#'
        row.append(reverse('sms_chat', args=[domain, contact_id, vn_id]))


@require_permission(HqPermissions.edit_messaging)
@requires_privilege_with_fallback(privileges.INBOUND_SMS)
def chat_contact_list(request, domain):
    sEcho = request.GET.get('sEcho')
    iDisplayStart = int(request.GET.get('iDisplayStart'))
    iDisplayLength = int(request.GET.get('iDisplayLength'))
    sSearch = request.GET.get('sSearch', '').strip()

    data = get_contact_info(domain)
    total_records = len(data)

    if sSearch:
        data = [row for row in data if sSearch in row[0] or sSearch in row[2]]
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

    return JsonResponse(result)


def get_contact_name_for_chat(contact, domain_obj):
    if is_commcarecase(contact):
        if domain_obj.custom_case_username:
            contact_name = contact.get_case_property(domain_obj.custom_case_username)
        else:
            contact_name = contact.name
    else:
        if contact.first_name:
            contact_name = contact.first_name
        else:
            contact_name = contact.raw_username
    return contact_name


@require_permission(HqPermissions.edit_messaging)
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

    contact = get_contact(domain, contact_id)

    context = {
        "domain": domain,
        "contact_id": contact_id,
        "contact": contact,
        "contact_name": get_contact_name_for_chat(contact, domain_obj),
        "use_message_counter": domain_obj.chat_message_count_threshold is not None,
        "message_count_threshold": domain_obj.chat_message_count_threshold or 0,
        "history_choices": history_choices,
        "vn_id": vn_id,
    }
    template = settings.CUSTOM_CHAT_TEMPLATES.get(domain_obj.custom_chat_template) or "sms/chat.html"
    return render(request, template, context)


class ChatMessageHistory(View, DomainViewMixin):
    urlname = 'api_history'

    @method_decorator(require_permission(HqPermissions.edit_messaging))
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(ChatMessageHistory, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def contact_id(self):
        return self.request.GET.get('contact_id')

    @property
    @memoized
    def contact(self):
        if not self.contact_id:
            return None

        try:
            return get_contact(self.domain, self.contact_id)
        except ContactNotFoundException:
            return None

    @property
    @memoized
    def contact_name(self):
        return get_contact_name_for_chat(self.contact, self.domain_object)

    @quickcache(['user_id'], timeout=60 * 60, memoize_timeout=5 * 60)
    def get_chat_user_name(self, user_id):
        if not user_id:
            return _("System")

        try:
            user = CouchUser.get_by_user_id(user_id)
            return user.first_name or user.raw_username
        except Exception:
            return _("Unknown")

    @property
    @memoized
    def start_date_str(self):
        return self.request.GET.get('start_date')

    @property
    @memoized
    def start_date(self):
        if not self.start_date_str:
            return None

        try:
            return iso_string_to_datetime(self.start_date_str)
        except (TypeError, ValueError):
            return None

    def get_raw_data(self):
        result = SMS.objects.filter(
            domain=self.domain,
            couch_recipient_doc_type=self.contact.doc_type,
            couch_recipient=self.contact_id
        ).exclude(
            direction=OUTGOING,
            processed=False
        )
        if self.start_date:
            result = result.filter(date__gt=self.start_date)
        result = self.filter_survey_data(result)
        return result.order_by('date')

    def filter_survey_data(self, queryset):
        if not self.domain_object.filter_surveys_from_chat:
            return queryset

        if self.domain_object.show_invalid_survey_responses_in_chat:
            return queryset.exclude(
                Q(xforms_session_couch_id__isnull=False)
                & ~Q(direction=INCOMING, invalid_survey_response=True)
            )
        else:
            return queryset.exclude(
                xforms_session_couch_id__isnull=False
            )

    def get_response_data(self, requesting_user_id):
        timezone = get_timezone_for_user(None, self.domain)
        result = []
        last_sms = None
        for sms in self.get_raw_data():
            last_sms = sms
            if sms.direction == INCOMING:
                sender = self.contact_name
            else:
                sender = self.get_chat_user_name(sms.chat_user_id)
            result.append({
                'sender': sender,
                'text': sms.text,
                'timestamp': (
                    ServerTime(sms.date).user_time(timezone)
                    .ui_string("%I:%M%p %m/%d/%y").lower()
                ),
                'utc_timestamp': json_format_datetime(sms.date),
                'sent_by_requester': (sms.chat_user_id == requesting_user_id),
            })
        return result, last_sms

    def update_last_read_message(self, requesting_user_id, sms):
        domain = self.domain
        contact_id = self.contact_id

        key = 'update-last-read-message-%s-%s-%s' % (domain, requesting_user_id, contact_id)
        with CriticalSection([key]):
            try:
                entry = SQLLastReadMessage.objects.get(
                    domain=domain,
                    read_by=requesting_user_id,
                    contact_id=contact_id
                )
            except SQLLastReadMessage.DoesNotExist:
                entry = SQLLastReadMessage(
                    domain=domain,
                    read_by=requesting_user_id,
                    contact_id=contact_id
                )
            if not entry.message_timestamp or entry.message_timestamp < sms.date:
                entry.message_id = sms.couch_id
                entry.message_timestamp = sms.date
                entry.save()

    def get(self, request, *args, **kwargs):
        if not self.contact:
            return JsonResponse([], safe=False)

        data, last_sms = self.get_response_data(request.couch_user.get_id)
        if last_sms:
            try:
                self.update_last_read_message(request.couch_user.get_id, last_sms)
            except Exception:
                notify_exception(request, "Error updating last read message for %s" % last_sms.pk)

        return JsonResponse(data, safe=False)


class ChatLastReadMessage(View, DomainViewMixin):
    urlname = 'api_last_read_message'

    @method_decorator(require_permission(HqPermissions.edit_messaging))
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(ChatLastReadMessage, self).dispatch(request, *args, **kwargs)

    @property
    @memoized
    def contact_id(self):
        return self.request.GET.get('contact_id')

    def get(self, request, *args, **kwargs):
        lrm_timestamp = None
        if self.contact_id:
            if self.domain_object.count_messages_as_read_by_anyone:
                lrm = SQLLastReadMessage.by_anyone(self.domain, self.contact_id)
            else:
                lrm = SQLLastReadMessage.by_user(self.domain, request.couch_user.get_id, self.contact_id)

            if lrm:
                lrm_timestamp = json_format_datetime(lrm.message_timestamp)
        return JsonResponse({
            'message_timestamp': lrm_timestamp,
        })


class DomainSmsGatewayListView(CRUDPaginatedViewMixin, BaseMessagingSectionView):
    template_name = "sms/gateway_list.html"
    urlname = 'list_domain_backends'
    page_title = gettext_noop("SMS Connectivity")
    strict_domain_fetching = True

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(DomainSmsGatewayListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

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
        mappings = SQLMobileBackendMapping.objects.filter(
            is_global=False,
            domain=self.domain,
            backend_type=SQLMobileBackend.SMS,
        )
        extra_backend_mappings = {
            mapping.prefix: mapping.backend.name
            for mapping in mappings if mapping.prefix != '*'
        }

        context = self.pagination_context

        context.update({
            'initiate_new_form': InitiateAddSMSBackendForm(
                user=self.request.couch_user,
                domain=self.domain
            ),
            'extra_backend_mappings': extra_backend_mappings,
            'is_system_admin': self.is_system_admin,
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
                    [_(country_name_for_country_code(int(c))) for c in backend.supported_countries])
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
            if hq_api_id == SQLTelerivetBackend.get_api_id():
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
    def is_system_admin(self):
        return is_superuser_or_contractor(self.request.couch_user)

    @property
    @memoized
    def hq_api_id(self):
        return self.kwargs.get('hq_api_id')

    @property
    @memoized
    def backend_class(self):
        # Superusers can create/edit any backend
        # Regular users can only create/edit Telerivet backends for now
        if not self.is_system_admin and self.hq_api_id != SQLTelerivetBackend.get_api_id():
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
            self.backend.display_name = self.backend_form.cleaned_data.get('display_name')
            self.backend.description = self.backend_form.cleaned_data.get('description')
            self.backend.reply_to_phone_number = self.backend_form.cleaned_data.get('reply_to_phone_number')

            extra_fields = {}
            for key, value in self.backend_form.cleaned_data.items():
                if key in self.backend.get_available_extra_fields():
                    extra_fields[key] = value
            self.backend.set_extra_fields(**extra_fields)

            if self.use_load_balancing:
                self.backend.load_balancing_numbers = self.backend_form.cleaned_data['phone_numbers']

            self.backend.opt_out_keywords = self.backend_form.cleaned_data.get('opt_out_keywords')
            self.backend.opt_in_keywords = self.backend_form.cleaned_data.get('opt_in_keywords')
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
    page_title = gettext_lazy("Add SMS Gateway")

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

    @method_decorator(domain_admin_required)
    @method_decorator(requires_privilege_with_fallback(privileges.OUTBOUND_SMS))
    def dispatch(self, request, *args, **kwargs):
        return super(AddDomainGatewayView, self).dispatch(request, *args, **kwargs)


class EditDomainGatewayView(AddDomainGatewayView):
    urlname = 'edit_domain_gateway'
    page_title = gettext_lazy("Edit SMS Gateway")

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
            backend.is_global
            or backend.domain != self.domain
            or backend.hq_api_id != self.backend_class.get_api_id()
            or backend.deleted
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
            'display_name': self.backend.display_name,
            'description': self.backend.description,
            'give_other_domains_access': len(authorized_domains) > 0,
            'authorized_domains': ','.join(authorized_domains),
            'reply_to_phone_number': self.backend.reply_to_phone_number,
            'opt_out_keywords': ','.join(self.backend.opt_out_keywords),
            'opt_in_keywords': ','.join(self.backend.opt_in_keywords),
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
    page_title = gettext_noop("SMS Connectivity")

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        if not has_privilege(request, privileges.GLOBAL_SMS_GATEWAY):
            return HttpResponseRedirect(
                reverse(
                    SMSAdminInterfaceDispatcher.name(),
                    kwargs={'report_slug': 'sms_billables'}
                )
            )
        return super(GlobalSmsGatewayListView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname)

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
            'initiate_new_form': InitiateAddSMSBackendForm(
                user=self.request.couch_user
            ),
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
                    [_(country_name_for_country_code(int(c))) for c in backend.supported_countries])
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
    page_title = gettext_lazy("Add SMS Gateway")

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

    @method_decorator(require_superuser)
    def dispatch(self, request, *args, **kwargs):
        if not has_privilege(request, privileges.GLOBAL_SMS_GATEWAY):
            return HttpResponseRedirect(reverse("no_permissions"))
        return super(AddGlobalGatewayView, self).dispatch(request, *args, **kwargs)


class EditGlobalGatewayView(AddGlobalGatewayView):
    urlname = 'edit_global_gateway'
    page_title = gettext_lazy("Edit SMS Gateway")

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
            not backend.is_global
            or backend.deleted
            or backend.hq_api_id != self.backend_class.get_api_id()
        ):
            raise Http404()
        return backend

    @property
    @memoized
    def backend_form(self):
        form_class = self.backend_class.get_form_class()
        initial = {
            'name': self.backend.name,
            'display_name': self.backend.display_name,
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
    page_title = gettext_noop("Subscribe SMS")

    @property
    def commtrack_settings(self):
        return Domain.get_by_name(self.domain).commtrack_settings

    @property
    @memoized
    def form(self):
        if self.request.method == 'POST':
            return SubscribeSMSForm(self.request.POST)

        if self.commtrack_settings and hasattr(self.commtrack_settings, 'alertconfig'):
            alert_config = self.commtrack_settings.alertconfig
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
    page_title = gettext_noop("Languages")

    @use_jquery_ui
    @method_decorator(domain_admin_required)
    def dispatch(self, *args, **kwargs):
        return super(SMSLanguagesView, self).dispatch(*args, **kwargs)

    @property
    def page_context(self):
        sms_translations = get_or_create_sms_translations(self.domain)
        context = {
            "domain": self.domain,
            "sms_langs": sms_translations.langs,
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
    with transaction.atomic():
        sms_translations = get_or_create_sms_translations(domain)
        try:
            from corehq.apps.app_manager.views.utils import validate_langs
            langs, rename = validate_langs(request, sms_translations.langs)
        except AssertionError:
            return HttpResponse(status=400)

        for old, new in rename.items():
            if old != new:
                sms_translations.translations[new] = sms_translations.translations[old]
                del sms_translations.translations[old]

        for lang in langs:
            if lang not in sms_translations.translations:
                sms_translations.translations[lang] = {}

        for lang in set(sms_translations.translations.keys()):
            if lang not in langs:
                del sms_translations.translations[lang]

        sms_translations.langs = langs
        sms_translations.save()
        return json_response(langs)


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
def download_sms_translations(request, domain):
    sms_translations = get_or_create_sms_translations(domain)
    columns = ["property"] + sms_translations.langs + ["default"]

    msg_ids = sorted(_MESSAGES.keys())
    rows = []
    for msg_id in msg_ids:
        rows.append([msg_id])

    for lang in sms_translations.langs:
        for row in rows:
            row.append(sms_translations.translations[lang].get(row[0], ""))

    for row in rows:
        row.append(_MESSAGES.get(row[0]))

    temp = io.BytesIO()
    headers = (("translations", tuple(columns)),)
    data = (("translations", tuple(rows)),)
    export_raw(headers, data, temp)
    return export_response(temp, Format.XLS_2007, "translations")


@domain_admin_required
@requires_privilege_with_fallback(privileges.OUTBOUND_SMS)
@get_file("bulk_upload_file")
def upload_sms_translations(request, domain):
    try:
        translations = get_single_worksheet(request.file, title='translations')

        with transaction.atomic():
            sms_translations = get_or_create_sms_translations(domain)
            msg_ids = sorted(_MESSAGES.keys())
            result = {lang: {} for lang in sms_translations.langs}

            for row in translations:
                for lang in sms_translations.langs:
                    msg_id = row["property"]
                    if row.get(lang) and msg_id in msg_ids:
                        val = str(row[lang])
                        val = val.strip()
                        result[lang][msg_id] = val

            sms_translations.translations = result
            sms_translations.save()
        messages.success(request, _("SMS Translations Updated."))
    except Exception:
        notify_exception(request, 'SMS Upload Translations Error')
        messages.error(request, _("Update failed. We're looking into it."))

    return HttpResponseRedirect(reverse('sms_languages', args=[domain]))


class SMSSettingsView(BaseMessagingSectionView, AsyncHandlerMixin):
    urlname = "sms_settings"
    template_name = "sms/settings.html"
    page_title = gettext_noop("SMS Settings")
    async_handlers = [SMSSettingsAsyncHandler]

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
            domain_obj.enable_registration_welcome_sms_for_case
            and domain_obj.enable_registration_welcome_sms_for_mobile_worker
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
            form = SettingsForm(
                self.request.POST,
                domain=self.domain,
                is_previewer=self.previewer,
            )
        else:
            domain_obj = Domain.get_by_name(self.domain, strict=True)
            enabled_disabled = lambda b: (ENABLED if b else DISABLED)  # noqa: E731
            default_custom = lambda b: (CUSTOM if b else DEFAULT)  # noqa: E731
            initial = {
                "use_default_sms_response":
                    enabled_disabled(domain_obj.use_default_sms_response),
                "default_sms_response":
                    domain_obj.default_sms_response,
                "use_restricted_sms_times":
                    enabled_disabled(len(domain_obj.restricted_sms_times) > 0),
                "restricted_sms_times_json":
                    [w.to_json() for w in domain_obj.restricted_sms_times],
                "sms_survey_date_format":
                    domain_obj.sms_survey_date_format,
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
                "sms_worker_registration_alert_emails": domain_obj.sms_worker_registration_alert_emails,
                "registration_welcome_message":
                    self.get_welcome_message_recipient(domain_obj),
                "language_fallback":
                    domain_obj.sms_language_fallback or LANGUAGE_FALLBACK_UNTRANSLATED,
                "override_daily_outbound_sms_limit":
                    ENABLED if domain_obj.custom_daily_outbound_sms_limit else DISABLED,
                "custom_daily_outbound_sms_limit":
                    domain_obj.custom_daily_outbound_sms_limit,
                "twilio_whatsapp_phone_number":
                    domain_obj.twilio_whatsapp_phone_number,
            }
            form = SettingsForm(
                initial=initial,
                domain=self.domain,
                is_previewer=self.previewer,
            )
        return form

    @property
    def page_context(self):
        return {
            "form": self.form,
        }

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response

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
                ("sms_survey_date_format",
                 "sms_survey_date_format"),
                ("sms_conversation_length",
                 "sms_conversation_length"),
                ("sms_language_fallback",
                 "language_fallback"),
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
                ("sms_worker_registration_alert_emails", "sms_worker_registration_alert_emails"),
            ]
            if self.previewer:
                field_map.extend([
                    ("custom_chat_template",
                     "custom_chat_template"),
                    ("custom_daily_outbound_sms_limit",
                     "custom_daily_outbound_sms_limit"),
                ])
            if toggles.WHATSAPP_MESSAGING.enabled(self.domain):
                field_map.extend([
                    ("twilio_whatsapp_phone_number",
                     "twilio_whatsapp_phone_number"),
                ])

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
            messages.success(request, _("Changes saved."))
        return self.get(request, *args, **kwargs)

    @method_decorator(domain_admin_required)
    @use_timepicker
    def dispatch(self, request, *args, **kwargs):
        return super(SMSSettingsView, self).dispatch(request, *args, **kwargs)


class IncomingBackendView(View):

    def __init__(self, *args, **kwargs):
        super(IncomingBackendView, self).__init__(*args, **kwargs)
        self.domain = None
        self.backend_couch_id = None

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

        return super(IncomingBackendView, self).dispatch(request, api_key, *args, **kwargs)


class WhatsAppTemplatesView(BaseMessagingSectionView):
    urlname = 'whatsapp_templates_view'
    template_name = "sms/whatsapp_templates.html"

    @method_decorator(domain_admin_required)
    def dispatch(self, request, *args, **kwargs):
        return super(WhatsAppTemplatesView, self).dispatch(request, *args, **kwargs)

    @property
    def page_context(self):
        context = super(WhatsAppTemplatesView, self).page_context
        from corehq.messaging.smsbackends.turn.models import SQLTurnWhatsAppBackend
        from corehq.messaging.smsbackends.infobip.models import InfobipBackend

        turn_backend = SQLTurnWhatsAppBackend.active_objects.filter(
            domain=self.domain,
            hq_api_id=SQLTurnWhatsAppBackend.get_api_id()
        )

        infobip_backend = InfobipBackend.active_objects.filter(
            domain=self.domain,
            hq_api_id=InfobipBackend.get_api_id()
        )

        if (turn_backend.count() + infobip_backend.count()) > 1:
            messages.error(
                self.request,
                _("You have multiple gateways that support whatsapp templates (infobip, turn) configured."
                  " Please remove the ones you don't use.")
            )
        elif (turn_backend.count() + infobip_backend.count()) == 0:
            messages.error(
                self.request,
                _("You have no gateways that support whatsapp templates (infobip, turn) configured."
                  " Please configure one before proceeding ")
            )
        else:
            wa_active_backend = turn_backend.get() if turn_backend.count() else infobip_backend.get()
            templates = wa_active_backend.get_all_templates()

            if templates is not None:
                for template in templates:
                    template['template_string'] = wa_active_backend.generate_template_string(template)
                context.update({'wa_templates': templates})
            else:
                messages.error(
                    self.request,
                    wa_active_backend.get_generic_name()
                    + _(" failed to fetch templates. Please make sure the gateway is configured properly.")
                )
        return context
