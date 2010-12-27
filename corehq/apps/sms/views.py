#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

from corehq.apps.users.models import CouchUser
from corehq.util.webutils import render_to_response

def messaging(request, domain, template="sms/default.html"):
    phone_users = CouchUser.view("users/phone_users_by_domain", key=domain)
    return render_to_response(request, template, {
        'domain': domain,
        'phone_users': [phone_user['value'] for phone_user in phone_users]
    })
