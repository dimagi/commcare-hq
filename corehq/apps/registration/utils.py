import logging
import uuid
from datetime import datetime
from django.core.mail import send_mail
from corehq.apps.registration.models import RegistrationRequest
from dimagi.utils.web import get_ip, get_url_base
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, CouchUser
from dimagi.utils.django.email import send_HTML_email

def activate_new_user(form, is_domain_admin=True, domain=None):
    username = form.cleaned_data['email']
    password = form.cleaned_data['password']
    full_name = form.cleaned_data['full_name']

    new_user = WebUser.create(domain, username, password, is_admin=is_domain_admin)
    new_user.first_name = full_name[0]
    new_user.last_name = full_name[1]
    new_user.email = username

    new_user.is_staff = False # Can't log in to admin site
    new_user.is_active = True
    new_user.is_superuser = False
    now = datetime.utcnow()
    new_user.last_login = now
    new_user.date_joined = now
    new_user.save()

    return new_user

def request_new_domain(request, form, org, new_user=True):
    now = datetime.utcnow()
    user_ip = get_ip(request)
    current_user = CouchUser.from_django_user(request.user)

    dom_req = RegistrationRequest()
    if new_user:
        dom_req.tos_confirmed = form.cleaned_data['eula_confirmed']
        dom_req.request_time = now
        dom_req.request_ip = user_ip
        dom_req.activation_guid = uuid.uuid1().hex

    new_domain = Domain(name=form.cleaned_data['domain_name'],
        is_active=False,
        date_created=datetime.utcnow())

    new_domain.eula.signed = True
    new_domain.eula.date = now
    new_domain.eula.type = 'End User License Agreement'
    if current_user:
        new_domain.eula.user_id = current_user.get_id
    new_domain.eula.user_ip = user_ip

    if org:
        new_domain.organization = org

    if not new_user:
        new_domain.is_active = True

    new_domain.save()
    if not new_domain.name:
        new_domain.name = new_domain._id
        new_domain.save() # we need to get the name from the _id

    dom_req.domain = new_domain.name

    if request.user.is_authenticated():
        if not current_user:
            current_user = WebUser()
            current_user.sync_from_django_user(request.user)
            current_user.save()
        current_user.add_domain_membership(new_domain.name, is_admin=True)
        current_user.save()
        dom_req.requesting_user_username = request.user.username
        dom_req.new_user_username = request.user.username

    if new_user:
        dom_req.save()
        send_domain_registration_email(request.user.email,
                                       dom_req.domain,
                                       dom_req.activation_guid)
    else:
        send_global_domain_registration_email(request.user, new_domain.name)
    send_new_domain_request_update_email(request.user, get_ip(request), new_domain.name, is_new_user=new_user)

def send_domain_registration_email(recipient, domain_name, guid):
    DNS_name = Site.objects.get(id = settings.SITE_ID).domain
    activation_link = 'http://' + DNS_name + reverse('registration_confirm_domain') + guid + '/'
    wiki_link = 'http://wiki.commcarehq.org/display/commcarepublic/Home'
    users_link = 'http://groups.google.com/group/commcare-users'

    message_plaintext = """
Welcome to CommCareHQ!

Please click this link:
{activation_link}
to activate your new domain.  You will not be able to use your domain until you have confirmed this email address.

Project name: "{domain}"

Username:  "{username}"

For help getting started, you can visit the CommCare Wiki, the home of all CommCare documentation.  Click this link to go directly to the guide to CommCare HQ:
{wiki_link}

We also encourage you to join the "commcare-users" google group, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list:
{users_link}

If you encounter any technical problems while using CommCareHQ, look for a "Report an Issue" link at the bottom of every page.  Our developers will look into the problem and communicate with you about a solution.

Thank you,

The CommCareHQ Team

"""

    message_html = """
<h1>Welcome to CommCare HQ!</h1>
<p>Please <a href="{activation_link}">go here to activate your new project</a>.  You will not be able to use your project until you have confirmed this email address.</p>
<p><strong>Project name:</strong> {domain}</p>
<p><strong>Username:</strong> {username}</p>
<p>For help getting started, you can visit the <a href="{wiki_link}">CommCare Wiki</a>, the home of all CommCare documentation.</p>
<p>We also encourage you to join the <a href="{users_link}">commcare-users google group</a>, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list.</p>
<p>If you encounter any technical problems while using CommCareHQ, look for a "Report an Issue" link at the bottom of every page.  Our developers will look into the problem and communicate with you about a solution.</p>
<p style="margin-top:1em">Thank you,</p>
<p><strong>The CommCareHQ Team</strong></p>
<p>If your email viewer won't permit you to click on the registration link above, cut and paste the following link into your web browser:</p>
{activation_link}
"""
    params = {"domain": domain_name, "activation_link": activation_link, "username": recipient, "wiki_link": wiki_link, "users_link": users_link}
    message_plaintext = message_plaintext.format(**params)
    message_html = message_html.format(**params)

    subject = 'Welcome to CommCare HQ!'.format(**locals())

    try:
        send_HTML_email(subject, recipient, message_plaintext, message_html)
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message_plaintext)


def send_global_domain_registration_email(requesting_user, domain_name):
    DNS_name = Site.objects.get(id = settings.SITE_ID).domain
    domain_link = 'http://' + DNS_name + reverse("domain_homepage", args=[domain_name])
    wiki_link = 'http://wiki.commcarehq.org/display/commcarepublic/Home'
    users_link = 'http://groups.google.com/group/commcare-users'

    message_plaintext = """
Hello {name},

You have successfully created and activated the project "{domain}" for the CommCare HQ user "{username}".

You may access your project by following this link: {domain_link}

Please remember, if you need help you can visit the CommCare Wiki, the home of all CommCare documentation.  Click this link to go directly to the guide to CommCare HQ:
{wiki_link}

If you haven't yet, we also encourage you to join the "commcare-users" google group, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list:
{users_link}

If you encounter any technical problems while using CommCareHQ, look for a "Report an Issue" link at the bottom of every page.  Our developers will look into the problem and communicate with you about a solution.

Thank you,

The CommCareHQ Team

"""

    message_html = """
<h1>New project "{domain}" created!</h1>
<p>Hello {name},</p>
<p>You may now  <a href="{domain_link}">visit your newly created project</a> with the CommCare HQ User <strong>{username}</strong>.</p>

<p>Please remember, if you need help you can visit the <a href="{wiki_link}">CommCare Wiki</a>, the home of all CommCare documentation.</p>
<p>We also encourage you to join the <a href="{users_link}">commcare-users google group</a>, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list.</p>
<p>If you encounter any technical problems while using CommCareHQ, look for a "Report an Issue" link at the bottom of every page.  Our developers will look into the problem and communicate with you about a solution.</p>
<p style="margin-top:1em">Thank you,</p>
<p><strong>The CommCareHQ Team</strong></p>
<p>If your email viewer won't permit you to click on the registration link above, cut and paste the following link into your web browser:</p>
{domain_link}
"""
    params = {"name": requesting_user.first_name, "domain": domain_name, "domain_link": domain_link, "username": requesting_user.email, "wiki_link": wiki_link, "users_link": users_link}
    message_plaintext = message_plaintext.format(**params)
    message_html = message_html.format(**params)

    subject = 'CommCare HQ: New project created!'.format(**locals())

    try:
        send_HTML_email(subject, requesting_user.email, message_plaintext, message_html)
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message_plaintext)

def send_new_domain_request_update_email(user, requesting_ip, domain_name, is_new_user=False, is_confirming=False):
    if is_confirming:
        message = "A (basically) brand new user just confirmed his/her account. The project space requested was %s." % domain_name
    elif is_new_user:
        message = "A brand new user just requested a project space called %s." % domain_name
    else:
        message = "An existing user just created a new project space called %s." % domain_name
    message = """%s

Details include...

Username: %s
IP Address: %s

You can view the project here: %s""" % (
        message,
        user.username,
        requesting_ip,
        get_url_base() + "/a/%s/" % domain_name)
    try:
        recipients = settings.NEW_DOMAIN_RECIPIENTS
        send_mail("New Project: %s" % domain_name, message, settings.EMAIL_LOGIN, recipients)
    except Exception:
        logging.warning("Can't send email, but the message was:\n%s" % message)
