import logging
import uuid
from datetime import date, datetime

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.translation import gettext

from celery import chord

from corehq.apps.users.role_utils import initialize_domain_with_default_roles
from corehq.util.soft_assert import soft_assert
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import get_safe_write_kwargs
from dimagi.utils.logging import notify_exception
from dimagi.utils.name_to_url import name_to_url
from dimagi.utils.web import get_ip, get_url_base, get_static_url_prefix

from corehq.apps.accounting.models import (
    BillingAccount,
    BillingContactInfo,
    SubscriptionAdjustmentMethod,
)
from corehq.apps.accounting.utils.subscription import ensure_community_or_paused_subscription
from corehq.apps.analytics.tasks import (
    HUBSPOT_CREATED_NEW_PROJECT_SPACE_FORM_ID,
    send_hubspot_form,
)
from corehq.apps.domain.exceptions import ErrorInitializingDomain
from corehq.apps.domain.models import Domain
from corehq.apps.hqmedia.models import LogoForSystemEmailsReference
from corehq.apps.hqwebapp.tasks import send_html_email_async, send_mail_async
from corehq.apps.registration.models import RegistrationRequest
from corehq.apps.registration.tasks import send_domain_registration_email
from corehq.apps.users.models import CouchUser, WebUser
from corehq.util.view_utils import absolute_reverse
from corehq.toggles import USE_LOGO_IN_SYSTEM_EMAILS

APPCUES_APP_SLUGS = ['health', 'agriculture', 'wash']

_soft_assert_registration_issues = soft_assert(
    to=[
        '{}@{}'.format(name, 'dimagi.com')
        for name in ['biyeun']
    ],
    exponential_backoff=False,
)


def activate_new_user_via_reg_form(form, created_by, created_via, is_domain_admin=False, domain=None, ip=None):
    full_name = form.cleaned_data['full_name']
    new_user = activate_new_user(
        username=form.cleaned_data['email'],
        password=form.cleaned_data['password'],
        created_by=created_by,
        created_via=created_via,
        first_name=full_name[0],
        last_name=full_name[1],
        is_domain_admin=is_domain_admin,
        domain=domain,
        ip=ip,
        atypical_user=form.cleaned_data.get('atypical_user', False),
    )
    return new_user


def activate_new_user(
    username, password, created_by, created_via, first_name=None, last_name=None,
    is_domain_admin=False, domain=None, ip=None, atypical_user=False
):
    now = datetime.utcnow()

    new_user = WebUser.create(
        domain,
        username,
        password,
        created_by,
        created_via,
        is_admin=is_domain_admin,
        by_domain_required_for_log=bool(domain),
    )
    new_user.first_name = first_name
    new_user.last_name = last_name
    new_user.email = username
    new_user.subscribed_to_commcare_users = False
    new_user.eula.signed = True
    new_user.eula.date = now
    new_user.eula.type = 'End User License Agreement'
    if ip:
        new_user.eula.user_ip = ip

    new_user.is_staff = False  # Can't log in to admin site
    new_user.is_active = True
    new_user.is_superuser = False
    new_user.last_login = now
    new_user.date_joined = now
    new_user.last_password_set = now
    new_user.atypical_user = atypical_user
    new_user.save()

    return new_user


def request_new_domain(request, project_name, is_new_user=True, is_new_sso_user=False):
    now = datetime.utcnow()
    current_user = CouchUser.from_django_user(request.user, strict=True)

    dom_req = RegistrationRequest()
    if is_new_user:
        dom_req.request_time = now
        dom_req.request_ip = get_ip(request)
        dom_req.activation_guid = uuid.uuid1().hex

    name = name_to_url(project_name, "project")
    with CriticalSection(['request_domain_name_{}'.format(name)]):
        name = Domain.generate_name(name)
        new_domain = Domain(
            name=name,
            hr_name=project_name,
            is_active=False,
            date_created=datetime.utcnow(),
            creating_user=current_user.username,
            secure_submissions=True,
            first_domain_for_user=is_new_user
        )

        # Avoid projects created by dimagi.com staff members as self started
        new_domain.internal.self_started = not current_user.is_dimagi

        if not is_new_user or is_new_sso_user:
            new_domain.is_active = True

        # ensure no duplicate domain documents get created on cloudant
        new_domain.save(**get_safe_write_kwargs())

    if not new_domain.name:
        new_domain.name = new_domain._id
        new_domain.save()  # we need to get the name from the _id
    dom_req.domain = new_domain.name

    if not settings.ENTERPRISE_MODE:
        try:
            _setup_subscription(new_domain.name, current_user)
        except Exception as error:
            # any error thrown in this process will cause the transaction.atomic() block that
            # the subscription setup is wrapped in to fail and any SQL changes related to the subscription
            # to roll back. Since we don't want a Subscription-less domain to exist, we should raise the
            # error and delete the domain.
            notify_exception(request, "Error initializing subscription for new domain", details={
                'domain': new_domain.name,
                'hr_name': project_name,
                'creating_user': current_user.username,
                'first_domain_for_user': is_new_user,
                'error': str(error),
            })
            new_domain.delete()
            raise ErrorInitializingDomain(f"Subscription setup failed for '{name}'")

    initialize_domain_with_default_roles(new_domain.name)

    if request.user.is_authenticated:
        if not current_user:
            current_user = WebUser()
            current_user.sync_from_django_user(request.user)
            current_user.save()
        current_user.add_domain_membership(new_domain.name, is_admin=True)
        current_user.save()
        dom_req.requesting_user_username = request.user.username
        dom_req.new_user_username = request.user.username
    elif is_new_user:
        _soft_assert_registration_issues(
            f"A new user {request.user.username} was not added to their domain "
            f"{new_domain.name} during registration"
        )

    if is_new_user and not is_new_sso_user:
        dom_req.save()
        if settings.IS_SAAS_ENVIRONMENT:
            #  Load template apps to the user's new domain in parallel
            from corehq.apps.app_manager.tasks import load_appcues_template_app
            header = [
                load_appcues_template_app.si(new_domain.name, current_user.username, slug)
                for slug in APPCUES_APP_SLUGS
            ]
            callback = send_domain_registration_email.si(
                request.user.email,
                dom_req.domain,
                dom_req.activation_guid,
                request.user.get_full_name(),
                request.user.first_name
            )
            chord(header)(callback)
        else:
            send_domain_registration_email(request.user.email,
                                           dom_req.domain,
                                           dom_req.activation_guid,
                                           request.user.get_full_name(),
                                           request.user.first_name)
    send_new_request_update_email(
        request.user,
        get_ip(request),
        new_domain.name,
        is_new_user=is_new_user,
        is_new_sso_user=is_new_sso_user
    )

    send_hubspot_form(HUBSPOT_CREATED_NEW_PROJECT_SPACE_FORM_ID, request)
    return new_domain.name


def _setup_subscription(domain_name, user):
    with transaction.atomic():
        ensure_community_or_paused_subscription(
            domain_name, date.today(), SubscriptionAdjustmentMethod.USER,
            web_user=user.username,
        )

    # add user's email as contact email for billing account for the domain
    account = BillingAccount.get_account_by_domain(domain_name)
    billing_contact, _ = BillingContactInfo.objects.get_or_create(account=account)
    billing_contact.email_list = [user.email]
    billing_contact.save()


def send_new_request_update_email(user, requesting_ip, entity_name, entity_type="domain",
                                  is_new_user=False, is_confirming=False, is_new_sso_user=False):
    entity_texts = {"domain": ["project space", "Project"],
                   "org": ["organization", "Organization"]}[entity_type]
    if is_new_sso_user:
        message = f"A new SSO user just requested a {entity_texts[0]} called {entity_name}."
    elif is_confirming:
        message = "A (basically) brand new user just confirmed his/her account. The %s requested was %s." % (
            entity_texts[0], entity_name)
    elif is_new_user:
        message = "A brand new user just requested a %s called %s." % (entity_texts[0], entity_name)
    else:
        message = "An existing user just created a new %s called %s." % (entity_texts[0], entity_name)
    message = """%s

Details include...

Username: %s
IP Address: %s

You can view the %s here: %s""" % (
        message,
        user.username,
        requesting_ip,
        entity_texts[0],
        get_url_base() + "/%s/%s/" % ("o" if entity_type == "org" else "a", entity_name))
    try:
        recipients = settings.NEW_DOMAIN_RECIPIENTS
        send_mail_async.delay(
            "New %s: %s" % (entity_texts[0], entity_name),
            message, recipients, from_email=settings.SERVER_EMAIL
        )
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message)


def project_logo_emails_context(domain, couch_user=None):
    if couch_user:
        user_domains = getattr(couch_user, 'domains', None)
        if user_domains:
            domain = user_domains[0]
    if domain and USE_LOGO_IN_SYSTEM_EMAILS.enabled(domain):
        try:
            image_reference = LogoForSystemEmailsReference.objects.get(domain=domain)
            return {
                "base_container_template": "registration/email/base_templates/_base_container_project_logo.html",
                "link_to_logo": image_reference.full_url_to_image()
            }
        except LogoForSystemEmailsReference.DoesNotExist:
            pass
    return {}


def send_mobile_experience_reminder(recipient, full_name, additional_email_context={}):
    url = absolute_reverse("login")

    params = {
        "full_name": full_name,
        "url": url,
        'url_prefix': get_static_url_prefix(),
    }
    params.update(additional_email_context)
    message_plaintext = render_to_string(
        'registration/email/mobile_signup_reminder.txt', params)
    message_html = render_to_string(
        'registration/email/mobile_signup_reminder.html', params)

    subject = gettext('Visit CommCareHQ on your computer!')

    try:
        send_html_email_async.delay(subject, recipient, message_html,
                                    text_content=message_plaintext,
                                    email_from=settings.DEFAULT_FROM_EMAIL)
    except Exception:
        logging.warning(
            "Can't send email, but the message was:\n%s" % message_plaintext)
        raise
