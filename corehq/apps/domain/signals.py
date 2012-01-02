from __future__ import absolute_import
from datetime import datetime
import logging
from corehq.apps.users.models import WebUser
from dimagi.utils.web import get_url_base
from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from corehq.apps.domain.models import Domain, CouchDomain, RegistrationRequest


def send_new_domain_email(sender, instance, created, **kwargs):
    if instance.confirm_time:
        domain = instance.domain
        user = instance.new_user or instance.requesting_user
        message = 'User %s from IP address %s just signed up for a new domain, %s (%s)' % (
            user.username,
            instance.confirm_ip,
            domain.name,
            get_url_base() + "/a/%s/" % domain
        )

        try:
            recipients = settings.NEW_DOMAIN_RECIPIENTS
            send_mail("New Domain: %s" % domain.name, message, settings.EMAIL_LOGIN, recipients)
        except Exception:
            logging.warning("Can't send email, but the message was:\n%s" % message)


def update_couch_domain(sender, instance, created, **kwargs):
    couch_domain = CouchDomain.view("domain/domains", key=instance.name, 
                                    reduce=False, include_docs=True).one()
    if couch_domain:
        if couch_domain.is_active != instance.is_active:
            couch_domain.is_active = instance.is_active
            couch_domain.save()
    else:
        couch_domain = CouchDomain(name=instance.name, 
                                   is_active=instance.is_active,
                                   is_public=False,
                                   date_created=datetime.utcnow())
        couch_domain.save()
    
post_save.connect(update_couch_domain, sender=Domain)
post_save.connect(send_new_domain_email, sender=RegistrationRequest)