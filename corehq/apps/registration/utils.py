from __future__ import absolute_import

import logging
from django.utils.translation import ugettext
import uuid
from datetime import datetime, date, timedelta
from django.template.loader import render_to_string
from corehq.apps.accounting.models import (
    SoftwarePlanEdition, DefaultProductPlan, BillingAccount, BillingContactInfo,
    BillingAccountType, Subscription, SubscriptionAdjustmentMethod, Currency,
    SubscriptionType, PreOrPostPay,
    DEFAULT_ACCOUNT_FORMAT,
)
from corehq.apps.accounting.tasks import ensure_explicit_community_subscription
from corehq.apps.registration.models import RegistrationRequest
from dimagi.utils.couch import CriticalSection
from dimagi.utils.name_to_url import name_to_url
from dimagi.utils.web import get_ip, get_url_base, get_site_domain
from django.conf import settings
from django.urls import reverse
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, CouchUser, UserRole
from corehq.apps.hqwebapp.tasks import send_html_email_async
from dimagi.utils.couch.database import get_safe_write_kwargs
from corehq.apps.hqwebapp.tasks import send_mail_async
from corehq.apps.analytics.tasks import send_hubspot_form, HUBSPOT_CREATED_NEW_PROJECT_SPACE_FORM_ID


def activate_new_user(form, is_domain_admin=True, domain=None, ip=None):
    username = form.cleaned_data['email']
    password = form.cleaned_data['password']
    full_name = form.cleaned_data['full_name']
    now = datetime.utcnow()

    new_user = WebUser.create(domain, username, password, is_admin=is_domain_admin)
    new_user.first_name = full_name[0]
    new_user.last_name = full_name[1]
    new_user.email = username
    new_user.email_opt_out = False  # auto add new users
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
    new_user.atypical_user = form.cleaned_data.get('atypical_user', False)
    new_user.save()

    return new_user


def request_new_domain(request, form, is_new_user=True):
    now = datetime.utcnow()
    current_user = CouchUser.from_django_user(request.user)

    dom_req = RegistrationRequest()
    if is_new_user:
        dom_req.request_time = now
        dom_req.request_ip = get_ip(request)
        dom_req.activation_guid = uuid.uuid1().hex

    project_name = form.cleaned_data.get('hr_name') or form.cleaned_data.get('project_name')
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
            use_sql_backend=True,
            first_domain_for_user=is_new_user
        )

        # Avoid projects created by dimagi.com staff members as self started
        new_domain.internal.self_started = not current_user.is_dimagi

        if form.cleaned_data.get('domain_timezone'):
            new_domain.default_timezone = form.cleaned_data['domain_timezone']

        if not is_new_user:
            new_domain.is_active = True

        # ensure no duplicate domain documents get created on cloudant
        new_domain.save(**get_safe_write_kwargs())

    if not new_domain.name:
        new_domain.name = new_domain._id
        new_domain.save()  # we need to get the name from the _id

    if is_new_user:
        # Only new-user domains are eligible for Advanced trial
        # domains with no subscription are equivalent to be on free Community plan
        create_30_day_advanced_trial(new_domain, current_user.username)
    else:
        ensure_explicit_community_subscription(new_domain.name, date.today())

    UserRole.init_domain_with_presets(new_domain.name)

    # add user's email as contact email for billing account for the domain
    account = BillingAccount.get_account_by_domain(new_domain.name)
    billing_contact, _ = BillingContactInfo.objects.get_or_create(account=account)
    billing_contact.email_list = [current_user.email]
    billing_contact.save()

    dom_req.domain = new_domain.name

    if request.user.is_authenticated:
        if not current_user:
            current_user = WebUser()
            current_user.sync_from_django_user(request.user)
            current_user.save()
        current_user.add_domain_membership(new_domain.name, is_admin=True)
        current_user.save()
        dom_req.requesting_user_username = request.user.username
        dom_req.new_user_username = request.user.username

    if is_new_user:
        dom_req.save()
        send_domain_registration_email(request.user.email,
                                       dom_req.domain,
                                       dom_req.activation_guid,
                                       request.user.get_full_name())
    send_new_request_update_email(request.user, get_ip(request), new_domain.name, is_new_user=is_new_user)

    send_hubspot_form(HUBSPOT_CREATED_NEW_PROJECT_SPACE_FORM_ID, request)
    return new_domain.name


REGISTRATION_EMAIL_BODY_HTML = u"""
<p><h2>30 Day Free Trial</h2></p>
<p>Welcome to your 30 day free trial! Evaluate all of our features for the next 30 days to decide which plan is right for you. Unless you subscribe to a paid plan, at the end of the 30 day trial you will be subscribed to the free Community plan. Read more about our pricing plans <a href="{pricing_link}">here</a>.</p>
<p><h2>Want to learn more?</h2></p>
<p>Check out our tutorials and other documentation on the <a href="{wiki_link}">CommCare Help Site</a>, the home of all CommCare documentation.</p>
<p><h2>Need Support?</h2></p>
<p>We encourage you to join the CommCare Users google group, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list. Subscribe <a href="{users_link}">here</a></p>
<p>If you encounter any technical problems while using CommCareHQ, look for a "Report an Issue" link at the bottom of every page. Our developers will look into the problem as soon as possible.</p>
<p>We hope you enjoy your experience with CommCareHQ!</p>
<p>The CommCareHQ Team</p>

<p>If your email viewer won't permit you to click on the link above, cut and paste the following link into your web browser:
{registration_link}
</p>
"""

REGISTRATION_EMAIL_BODY_PLAINTEXT = u"""
30 Day Free Trial

Welcome to your 30 day free trial! Evaluate all of our features for the next 30 days to decide which plan is right for you. Unless you subscribe to a paid plan, at the end of the 30 day trial you will be subscribed to the free Community plan. Read more about our pricing plans:
{pricing_link}

Want to learn more?

Check out our tutorials and other documentation on the CommCare Help Site, the home of all CommCare documentation:
{wiki_link}

Need Support?

We encourage you to join the CommCare Users google group, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list. Subscribe here:
{users_link}

If you encounter any technical problems while using CommCareHQ, look for a "Report an Issue" link at the bottom of every page. Our developers will look into the problem as soon as possible.

We hope you enjoy your experience with CommCareHQ!

The CommCareHQ Team

"""


WIKI_LINK = 'http://help.commcarehq.org'
USERS_LINK = 'http://groups.google.com/group/commcare-users'
PRICING_LINK = 'https://www.commcarehq.org/pricing'


def send_domain_registration_email(recipient, domain_name, guid, full_name):
    DNS_name = get_site_domain()
    registration_link = 'http://' + DNS_name + reverse('registration_confirm_domain') + guid + '/'

    params = {
        "domain": domain_name,
        "pricing_link": PRICING_LINK,
        "registration_link": registration_link,
        "full_name": full_name,
        "users_link": USERS_LINK,
        "wiki_link": WIKI_LINK,
        'url_prefix': '' if settings.STATIC_CDN else 'http://' + DNS_name,
    }
    message_plaintext = render_to_string('registration/email/confirm_account.txt', params)
    message_html = render_to_string('registration/email/confirm_account.html', params)

    subject = ugettext('Activate your CommCare project')

    try:
        send_html_email_async.delay(subject, recipient, message_html,
                                    text_content=message_plaintext,
                                    email_from=settings.DEFAULT_FROM_EMAIL,
                                    ga_track=True)
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message_plaintext)


def send_new_request_update_email(user, requesting_ip, entity_name, entity_type="domain", is_new_user=False, is_confirming=False):
    entity_texts = {"domain": ["project space", "Project"],
                   "org": ["organization", "Organization"]}[entity_type]
    if is_confirming:
        message = "A (basically) brand new user just confirmed his/her account. The %s requested was %s." % (entity_texts[0], entity_name)
    elif is_new_user:
        message = "A brand new user just requested a %s called %s." % (entity_texts[0], entity_name)
    else:
        message = "An existing user just created a new %s called %s." % (entity_texts[0], entity_name)
    message = u"""%s

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
            u"New %s: %s" % (entity_texts[0], entity_name),
            message, settings.SERVER_EMAIL, recipients
        )
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message)


# Only new-users are eligible for advanced trial
def create_30_day_advanced_trial(domain_obj, creating_username):
    # Create a 30 Day Trial subscription to the Advanced Plan
    advanced_plan_version = DefaultProductPlan.get_default_plan_version(
        edition=SoftwarePlanEdition.ADVANCED, is_trial=True
    )
    expiration_date = date.today() + timedelta(days=30)
    trial_account = BillingAccount.objects.get_or_create(
        name=DEFAULT_ACCOUNT_FORMAT % domain_obj.name,
        currency=Currency.get_default(),
        created_by=creating_username,
        created_by_domain=domain_obj.name,
        account_type=BillingAccountType.USER_CREATED,
        pre_or_post_pay=PreOrPostPay.POSTPAY,
    )[0]
    trial_subscription = Subscription.new_domain_subscription(
        trial_account, domain_obj.name, advanced_plan_version,
        date_end=expiration_date,
        adjustment_method=SubscriptionAdjustmentMethod.TRIAL,
        is_trial=True,
        service_type=SubscriptionType.TRIAL
    )
    trial_subscription.is_active = True
    trial_subscription.save()
