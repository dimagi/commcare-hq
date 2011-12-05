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
    link = 'http://' + DNS_name + reverse('registration_confirm_domain') + guid + '/'

    message_plaintext = """
You requested the new HQ domain "{domain}". To activate this domain, navigate to the following link
{link}
Thereafter, you'll be able to log on to your new domain with the email "{username}".
"""

    message_html = """
<p>You requested the new CommCare HQ domain "{domain}".</p>
<p>To activate this domain, click on <a href="{link}">this link</a>.</p>
<p>If your email viewer won't permit you to click on that link, cut and paste the following link into your web browser:</p>
<p>{link}</p>
<p>Thereafter, you'll be able to log on to your new domain with the email "{username}".</p>
"""
    params = {"domain": domain_name, "link": link, "username": recipient}
    message_plaintext = message_plaintext.format(**params)
    message_html = message_html.format(**params)

    subject = 'CommCare HQ Domain Request ({domain_name})'.format(**locals())

    send_HTML_email(subject, recipient, message_plaintext, message_html)
