import uuid
from datetime import datetime
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from corehq.apps.domain.models import RegistrationRequest, Domain
from corehq.apps.users.models import WebUser, CouchUser
from dimagi.utils.django.email import send_HTML_email

def activate_new_user(form):
    username = form.cleaned_data['email']
    password = form.cleaned_data['password']
    full_name = form.cleaned_data['full_name']

    new_user = WebUser.create(None, username, password, is_admin=True)
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

def request_new_domain(request, form):
    now = datetime.utcnow()

    dom_req = RegistrationRequest()
    dom_req.tos_confirmed = form.cleaned_data['tos_confirmed']
    dom_req.request_time = now
    dom_req.request_ip = request.META['REMOTE_ADDR']
    dom_req.activation_guid = uuid.uuid1().hex

    new_domain = Domain(name=form.cleaned_data['domain_name'], is_active=False)
    new_domain.save()
    dom_req.domain = new_domain

    if request.user.is_authenticated():
        current_user = CouchUser.from_django_user(request.user)
        current_user.add_domain_membership(new_domain.name, is_admin=True)
        current_user.save()
        dom_req.requesting_user = request.user
        dom_req.new_user = request.user

    dom_req.save()
    send_domain_registration_email(dom_req.requesting_user.email,
                                   dom_req.domain.name,
                                   dom_req.activation_guid)

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

Domain name: "{domain}"

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
<p>Please <a href="{activation_link}">go here to activate your new domain</a>.  You will not be able to use your domain until you have confirmed this email address.</p>
<p><strong>Domain name:</strong> {domain}</p>
<p><strong>Username:</strong> {username}</p>
<p>For help getting started, you can visit the <a href="{wiki_link}">CommCare Wiki</a>, the home of all CommCare documentation.
<p>We also encourage you to join the <a href="{users_link}">commcare-users google group</a>, where CommCare users from all over the world ask each other questions and share information over the commcare-users mailing list:</a>
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

    send_HTML_email(subject, recipient, message_plaintext, message_html)
